"""火山引擎双向流式语音合成客户端(豆包语音合成大模型 seed-tts-2.0)

协议: wss://openspeech.bytedance.com/api/v3/tts/bidirection
文本流式输入(逐段喂给 LLM 的增量), 音频流式输出(PCM 块); 
服务端自动分句合成, 无需客户端切句 
"""
import json
import uuid
from typing import AsyncIterator

import websockets

from app.services.volcano_protocol import (
    Message, MsgType, MsgFlag, Event, Serialization, encode_json_message,
)

TTS_URL = "wss://openspeech.bytedance.com/api/v3/tts/bidirection"


class VolcanoTTSError(RuntimeError):
    """TTS 服务异常"""


class VolcanoTTSSession:
    """一次回复对应一个 TTS 合成会话(同一连接可复用多轮 session)"""

    def __init__(self, api_key: str, resource_id: str, speaker: str, sample_rate: int = 24000,
                 speech_rate: int = 0):
        self._api_key = api_key
        self._resource_id = resource_id
        self._speaker = speaker
        self._sample_rate = sample_rate
        self._speech_rate = speech_rate  # [-50, 100], 100=2.0倍速
        self._ws = None
        self._session_id = ""

    async def start(self) -> None:
        """建立连接并开启合成会话"""
        self._ws = await websockets.connect(
            TTS_URL,
            extra_headers={
                "X-Api-Key": self._api_key,
                "X-Api-Resource-Id": self._resource_id,
                "X-Api-Connect-Id": str(uuid.uuid4()),
            },
            max_size=10 * 1024 * 1024,
        )
        await self._ws.send(encode_json_message(
            MsgType.FullClientRequest, {}, flag=MsgFlag.WithEvent, event=Event.StartConnection,
        ))
        await self._wait_event(Event.ConnectionStarted)

        self._session_id = str(uuid.uuid4())
        await self._ws.send(encode_json_message(
            MsgType.FullClientRequest,
            {
                "event": int(Event.StartSession),
                "req_params": {
                    "speaker": self._speaker,
                    "audio_params": {
                        "format": "pcm",
                        "sample_rate": self._sample_rate,
                        "speech_rate": self._speech_rate,
                    },
                    # additions 必须是 JSON 字符串(火山 Go 服务端定义为 string 类型)
                    # 朗读时剥离 Markdown 语法; 保留 emoji: 火山 TTS 会识别心情类 emoji 并带情感朗读(实测有效)
                    "additions": json.dumps(
                        {"disable_markdown_filter": True, "disable_emoji_filter": False}
                    ),
                },
            },
            flag=MsgFlag.WithEvent, event=Event.StartSession, session_id=self._session_id,
        ))
        await self._wait_event(Event.SessionStarted)

    async def send_text(self, text: str) -> None:
        """流式喂入待合成文本(可直接传 LLM 增量); 会话已关闭时静默跳过(打断竞态)"""
        if not text or self._ws is None:
            return
        await self._ws.send(encode_json_message(
            MsgType.FullClientRequest,
            {"event": int(Event.TaskRequest), "req_params": {"text": text}},
            flag=MsgFlag.WithEvent, event=Event.TaskRequest, session_id=self._session_id,
        ))

    async def finish_text(self) -> None:
        """文本输入结束, 等待剩余音频合成; 会话已关闭时静默跳过(打断竞态)"""
        if self._ws is None:
            return
        await self._ws.send(encode_json_message(
            MsgType.FullClientRequest,
            {"event": int(Event.FinishSession)},
            flag=MsgFlag.WithEvent, event=Event.FinishSession, session_id=self._session_id,
        ))

    async def audio_chunks(self) -> AsyncIterator[bytes]:
        """持续产出合成音频块(PCM), 直到 SessionFinished; 会话已关闭时立即结束"""
        while True:
            if self._ws is None:
                return
            raw = await self._ws.recv()
            if isinstance(raw, str):
                raise VolcanoTTSError(f"TTS 服务错误: {raw[:200]}")
            msg = Message.parse(raw)
            if msg.type == MsgType.Error:
                raise VolcanoTTSError(f"TTS 服务错误: {msg.payload.decode('utf-8', 'ignore')[:200]}")
            if msg.type == MsgType.AudioOnlyServer and msg.event == Event.TTSResponse:
                if msg.payload:
                    yield msg.payload
            elif msg.event == Event.SessionFinished:
                break
            elif msg.event == Event.SessionFailed:
                raise VolcanoTTSError("TTS 会话失败")

    async def cancel(self) -> None:
        """取消会话(打断场景): 尽力发送取消事件后立即断开"""
        try:
            await self._ws.send(encode_json_message(
                MsgType.FullClientRequest,
                {"event": int(Event.CancelSession)},
                flag=MsgFlag.WithEvent, event=Event.CancelSession, session_id=self._session_id,
            ))
        except Exception:
            pass
        await self.close()

    async def close(self) -> None:
        if self._ws is not None:
            try:
                await self._ws.send(encode_json_message(
                    MsgType.FullClientRequest,
                    {"event": int(Event.FinishConnection)},
                    flag=MsgFlag.WithEvent, event=Event.FinishConnection,
                ))
            except Exception:
                pass
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

    async def _wait_event(self, event: Event) -> Message:
        """等待指定服务端事件, 其他事件跳过"""
        while True:
            raw = await self._ws.recv()
            if isinstance(raw, str):
                raise VolcanoTTSError(f"TTS 服务错误: {raw[:200]}")
            msg = Message.parse(raw)
            if msg.type == MsgType.Error:
                raise VolcanoTTSError(f"TTS 服务错误: {msg.payload.decode('utf-8', 'ignore')[:200]}")
            if msg.event == Event.SessionFailed:
                raise VolcanoTTSError("TTS 会话失败")
            if msg.event == Event.ConnectionFailed:
                raise VolcanoTTSError("TTS 连接失败")
            if msg.event == event:
                return msg
