"""客服语音通话网关(服务端)

浏览器 ◀─ WebSocket ─▶ 本网关 ◀─ WebSocket ─▶ 火山流式 ASR / 双向流式 TTS
                        │
                        └─ 每句对话复用 chat_stream(工具循环/会话记忆/落库不变)

浏览器 → 网关: 二进制帧 = PCM 16k 16bit mono 麦克风音频(约200ms/帧, 直接透传 ASR); 
        文本帧 = JSON 控制: {"type":"stop"} 挂断、{"type":"audio_played"} 本句音频已播完、{"type":"barge_in"} 用户开口打断
网关 → 浏览器(JSON 文本帧): 
  {"type":"status","phase":"listening|thinking|speaking"}
  {"type":"subtitle","text":..}                  ASR 实时字幕(增量累计文本)
  {"type":"final","text":..}                     一句说完的确定文本
  {"type":"assistant_delta","text":..}           回复文本增量
  {"type":"assistant_text","text":..}            本句完整回复
  {"type":"tool","display":..}                   工具调用状态
  {"type":"audio","pcm":"<base64 PCM 24k>"}      TTS 音频块
  {"type":"audio_done"}                          本句音频下发完毕
  {"type":"interrupted"}                         用户开口, 已打断
  {"type":"error","message":..}

并发模型: 
  主循环      接收浏览器音频二进制帧 → 透传 ASR(全双工, AI 说话时麦克风持续上行)
  asr_reader  监听识别结果: definite 分句入队; speaking 期间有确定新语音即打断
  round_runner顺序执行每轮对话(被打断的轮次直接废弃, 不落库)
"""
import asyncio
import base64
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings
from app.database import SessionLocal
from app.models.user import User
from app.models.chat import ChatSession
from app.utils.security import verify_access_token
from app.services.chat_service import ChatService
from app.services.volcano_asr import VolcanoASRSession, VolcanoASRError
from app.services.volcano_tts import VolcanoTTSSession, VolcanoTTSError

logger = logging.getLogger("voice_call")
router = APIRouter()

PHASE_LISTENING = "listening"
PHASE_THINKING = "thinking"
PHASE_SPEAKING = "speaking"


async def _send_json(ws: WebSocket, data: dict) -> None:
    try:
        await ws.send_text(json.dumps(data, ensure_ascii=False, default=str))
    except Exception:
        pass


async def _authorize(user_id: int, session_id: int) -> bool:
    """校验用户有效性与会话归属"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id, User.status == 1).first()
        if not user:
            return False
        chat_session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id, ChatSession.user_id == user_id
        ).first()
        return chat_session is not None
    finally:
        db.close()


async def run_call(ws: WebSocket, user_id: int, chat_session_id: int) -> None:
    """一次语音通话的主循环"""
    asr = VolcanoASRSession(settings.VOLCANO_API_KEY, settings.VOLCANO_ASR_RESOURCE_ID)

    phase = {"value": PHASE_LISTENING}
    stop_event = asyncio.Event()
    utterance_queue: asyncio.Queue = asyncio.Queue()
    round_task: asyncio.Task | None = None
    muted = {"value": False}               # 打断后静音标志: 剩余文本不再播报, 轮次照常跑完
    current = {"pump": None, "tts": None}  # 当前轮的音频泵与 TTS 会话(打断时需立即停止)

    async def announce(new_phase: str) -> None:
        phase["value"] = new_phase
        await _send_json(ws, {"type": "status", "phase": new_phase})

    async def interrupt_if_speaking() -> None:
        """用户在 AI 说话时开口: 立即停止播报(静音), 当前轮次后台跑完 

        轮次里的工具调用(改购物车等)与消息落库必须完整执行, 因此只静音、不取消任务; 
        用户打断时说的新话语已进入队列, 本轮结束后立即处理 
        """
        if phase["value"] == PHASE_SPEAKING and round_task and not round_task.done():
            muted["value"] = True
            pump = current["pump"]
            if pump and not pump.done():
                pump.cancel()
            if current["tts"]:
                await current["tts"].cancel()
            await _send_json(ws, {"type": "interrupted"})
        if phase["value"] != PHASE_LISTENING:
            await announce(PHASE_LISTENING)

    async def pump_tts_audio(tts: VolcanoTTSSession) -> None:
        """把 TTS 合成音频块转发给浏览器(本句的下行音频)"""
        first = True
        async for chunk in tts.audio_chunks():
            if first:
                await announce(PHASE_SPEAKING)
                first = False
            await _send_json(ws, {"type": "audio", "pcm": base64.b64encode(chunk).decode()})
        await _send_json(ws, {"type": "audio_done"})

    async def run_round(text: str) -> None:
        """一轮对话: chat_stream → TTS → 音频回传(被打断仅静音, 轮次照常跑完)"""
        db = SessionLocal()
        svc = ChatService(db)
        # 每轮独立 TTS 会话: FinishSession 后旧会话即终结, 第二轮必须重新 StartSession
        tts = VolcanoTTSSession(
            settings.VOLCANO_API_KEY,
            settings.VOLCANO_TTS_RESOURCE_ID,
            settings.VOLCANO_TTS_SPEAKER,
            settings.VOLCANO_TTS_SAMPLE_RATE,
            settings.VOLCANO_TTS_SPEECH_RATE,
        )
        audio_pump: asyncio.Task | None = None
        muted["value"] = False
        try:
            await announce(PHASE_THINKING)
            await tts.start()
            audio_pump = asyncio.create_task(pump_tts_audio(tts))
            current["pump"] = audio_pump
            current["tts"] = tts
            parts = []
            async for ev in svc.chat_stream(user_id, chat_session_id, text):
                if ev["type"] == "delta":
                    parts.append(ev["content"])
                    if not muted["value"]:
                        await tts.send_text(ev["content"])
                        await _send_json(ws, {"type": "assistant_delta", "text": ev["content"]})
                elif ev["type"] == "tool":
                    if not muted["value"]:
                        await _send_json(ws, {"type": "tool", "display": ev.get("display")})
                elif ev["type"] == "done":
                    full_text = "".join(parts)
                    if not muted["value"]:
                        await tts.finish_text()
                        await _send_json(ws, {"type": "assistant_text", "text": full_text})
                elif ev["type"] == "error":
                    raise VolcanoTTSError(ev.get("message") or "客服处理异常")
            try:
                await asyncio.shield(audio_pump)
            except asyncio.CancelledError:
                # 音频泵被打断取消 → 吞掉继续收尾; 轮次自身被取消(挂断)→ 向上传播
                if not audio_pump.cancelled():
                    raise
            if phase["value"] == PHASE_THINKING:
                # 本轮未产出任何音频(如空回复)→ 直接回到聆听
                await announce(PHASE_LISTENING)
        except asyncio.CancelledError:
            if audio_pump:
                audio_pump.cancel()
            await tts.cancel()
            raise
        except (VolcanoTTSError, VolcanoASRError) as e:
            if audio_pump:
                audio_pump.cancel()
            if not muted["value"]:
                await _send_json(ws, {"type": "error", "message": str(e)})
        except Exception:
            logger.exception("语音通话轮次异常")
            if audio_pump:
                audio_pump.cancel()
            if not muted["value"]:
                await _send_json(ws, {"type": "error", "message": "客服处理异常"})
        finally:
            await tts.close()
            db.close()

    async def round_runner() -> None:
        """顺序消费识别出的分句, 逐轮执行对话"""
        nonlocal round_task
        while not stop_event.is_set():
            text = await utterance_queue.get()
            round_task = asyncio.create_task(run_round(text))
            try:
                await round_task
            except asyncio.CancelledError:
                pass  # 被打断, run_round 内部已清理
            round_task = None

    async def asr_reader() -> None:
        """监听 ASR 结果: 实时字幕 + 分句判停触发对话/打断"""
        last_text = ""
        try:
            while True:
                result = await asr.receive()
                if result is None:
                    continue
                text = result.get("text", "")
                if text and text != last_text:
                    await _send_json(ws, {"type": "subtitle", "text": text})
                last_text = text

                # 仅处理新增的 definite 分句(服务端全量列表会重复带回旧分句)
                for definite in result.get("definite_texts") or []:
                    await interrupt_if_speaking()
                    await _send_json(ws, {"type": "final", "text": definite})
                    await utterance_queue.put(definite)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            # 识别任务死亡必须显式暴露, 否则前端会永远停在"聆听中"
            logger.error("ASR 识别任务异常终止: %s", e)
            await _send_json(ws, {"type": "error", "message": f"语音识别中断: {e}"})

    await asr.start()
    await announce(PHASE_LISTENING)

    asr_task = asyncio.create_task(asr_reader())
    runner_task = asyncio.create_task(round_runner())

    try:
        # 主循环: 接收浏览器消息(二进制=麦克风音频透传 ASR; 文本=控制指令)
        audio_frames = 0
        while True:
            message = await ws.receive()
            if message["type"] == "websocket.disconnect":
                break
            if message.get("bytes") is not None:
                if message["bytes"]:
                    audio_frames += 1
                    if audio_frames % 25 == 1:
                        logger.info("已转发上行音频帧 %s(每帧 200ms)", audio_frames)
                    await asr.send_audio(message["bytes"])
            elif message.get("text") is not None:
                try:
                    frame = json.loads(message["text"])
                except json.JSONDecodeError:
                    continue
                if frame.get("type") == "stop":
                    break
                if frame.get("type") == "barge_in":
                    # 前端本地能量检测到用户开口, 立即打断当前播报(不等 ASR definite)
                    await interrupt_if_speaking()
                if frame.get("type") == "audio_played" and phase["value"] == PHASE_SPEAKING:
                    # 浏览器已播完本句音频 → 回到聆听状态
                    await announce(PHASE_LISTENING)
    except WebSocketDisconnect:
        pass
    finally:
        stop_event.set()
        asr_task.cancel()
        runner_task.cancel()
        if round_task and not round_task.done():
            round_task.cancel()
        for task in (asr_task, runner_task, round_task):
            if task:
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
        await asr.close()
        try:
            await ws.close()
        except Exception:
            pass


@router.websocket("/call")
async def voice_call(ws: WebSocket) -> None:
    """语音通话入口 query: ?token=<access_token>&session=<chat_session_id>"""
    await ws.accept()
    if not settings.VOICE_CALL_ENABLED:
        await _send_json(ws, {"type": "error", "message": "语音通话未启用, 请先配置 VOLCANO_API_KEY"})
        await ws.close()
        return

    payload = verify_access_token(ws.query_params.get("token") or "")
    user_id = int(payload["sub"]) if payload and payload.get("sub") else 0
    session_id = int(ws.query_params.get("session", "0") or 0)

    if not user_id or not await _authorize(user_id, session_id):
        await _send_json(ws, {"type": "error", "message": "未授权或会话不存在"})
        await ws.close()
        return

    try:
        await run_call(ws, user_id, session_id)
    except Exception:
        logger.exception("语音通话连接异常")
        try:
            await ws.close()
        except Exception:
            pass
