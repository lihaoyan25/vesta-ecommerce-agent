"""火山引擎双向流式语音识别客户端(豆包流式语音识别 bigmodel_async)

协议: wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async
音频流式输入(PCM 16k, 200ms/包), 实时返回识别结果; 
开启二遍识别后 VAD 分句判停时返回 definite=True 的最终分句 
"""
import json
import uuid
from typing import AsyncIterator, Dict, Any, Optional

import websockets

from app.services.volcano_protocol import (
    Message, MsgType, MsgFlag, encode_json_message, encode_audio,
)

ASR_URL = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async"


class VolcanoASRError(RuntimeError):
    """ASR 服务异常"""


class VolcanoASRSession:
    """一次通话对应一个 ASR 会话, 持续接收麦克风音频并产出识别结果"""

    def __init__(self, api_key: str, resource_id: str, uid: str = "vesta-voice-call"):
        self._api_key = api_key
        self._resource_id = resource_id
        self._uid = uid
        self._ws = None
        self._definite_seen = 0  # 已消费的 definite 分句数(服务端每条消息都携带全量列表)

    async def start(self) -> None:
        """建立连接并发送会话配置"""
        self._ws = await websockets.connect(
            ASR_URL,
            extra_headers={
                "X-Api-Key": self._api_key,
                "X-Api-Resource-Id": self._resource_id,
                "X-Api-Request-Id": str(uuid.uuid4()),
                "X-Api-Connect-Id": str(uuid.uuid4()),
            },
            max_size=10 * 1024 * 1024,
        )
        payload = {
            "user": {"uid": self._uid},
            "audio": {"format": "pcm", "codec": "raw", "rate": 16000, "bits": 16, "channel": 1},
            "request": {
                "model_name": "bigmodel",
                "enable_punc": True,
                # 二遍识别: 实时出字 + VAD 判停后非流式二次识别, definite 标记最终分句
                "enable_nonstream": True,
                "show_utterances": True,
            },
        }
        await self._ws.send(encode_json_message(
            MsgType.FullClientRequest, payload, compress=True,
        ))

    async def send_audio(self, pcm: bytes, *, last: bool = False) -> None:
        """发送一帧麦克风音频; last=True 发送末包结束本次识别"""
        await self._ws.send(encode_audio(pcm, last=last))

    async def receive(self) -> Optional[Dict[str, Any]]:
        """接收一帧服务端消息 

        返回 {"text": 累计识别文本, "definite_texts": 新确认的分句文本列表}; 
        无业务结果时返回 None; 服务报错时抛 VolcanoASRError 
        注意: 服务端每条消息的 utterances 都是全量列表(definite 分句持续留存), 
        必须按数量增量截取, 否则同一分句会被反复返回; 按文本去重不可行(同一句话可能说两遍) 
        """
        raw = await self._ws.recv()
        if isinstance(raw, str):
            raise VolcanoASRError(f"ASR 服务错误: {raw[:200]}")
        msg = Message.parse(raw)
        if msg.type == MsgType.Error:
            raise VolcanoASRError(f"ASR 服务错误: {msg.payload.decode('utf-8', 'ignore')[:200]}")
        if msg.type != MsgType.FullServerResponse:
            # 服务端确认帧等, 无业务结果
            return None
        try:
            data = json.loads(msg.payload)
        except json.JSONDecodeError:
            return None
        result = data.get("result") or {}
        utterances = result.get("utterances") or []
        definite_utterances = [u for u in utterances if u.get("definite")]
        new_definite = [u.get("text", "") for u in definite_utterances[self._definite_seen:]]
        self._definite_seen = len(definite_utterances)
        return {"text": result.get("text", ""), "definite_texts": new_definite}

    async def finish(self) -> None:
        """发送末包, 结束识别输入"""
        await self.send_audio(b"", last=True)

    async def close(self) -> None:
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *exc):
        await self.close()
