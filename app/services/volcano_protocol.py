"""火山引擎语音 WebSocket v3 二进制协议编解码

帧结构(对照官方 demo protocols.py): 
    [4 字节头][可选扩展][4 字节 payload size][payload]
    - Byte0: (version << 4) | header_size
    - Byte1: (msg_type << 4) | flag
    - Byte2: (serialization << 4) | compression
    - Byte3: 保留
    - flag=WithEvent 时, 扩展字段依次为: event(int32) → session_id(int32长度+字节), 
      连接类事件不携带 session_id
    - 所有整数字段大端; gzip 压缩仅作用于 payload

事件号规则: 1~49 上行连接, 50~99 下行连接, 100~149 上行会话, 
150~199 下行会话, 200~249 上行通用, 250~299 下行通用, 300+ 业务事件 
"""
import gzip
import json
import struct
from dataclasses import dataclass, field
from enum import IntEnum


class MsgType(IntEnum):
    FullClientRequest = 0b0001
    AudioOnlyClient = 0b0010
    FullServerResponse = 0b1001
    AudioOnlyServer = 0b1011
    FrontEndResultServer = 0b1100
    Error = 0b1111


class MsgFlag(IntEnum):
    NoSeq = 0b0000            # 非末包, 无序号
    PositiveSeq = 0b0001      # 非末包, 带正序号
    LastNoSeq = 0b0010        # 末包, 无序号
    NegativeSeq = 0b0011      # 末包, 带负序号
    WithEvent = 0b0100        # payload 前带 event 号(int32)


class Serialization(IntEnum):
    Raw = 0b0000
    JSON = 0b0001


class Compression(IntEnum):
    NONE = 0b0000
    GZIP = 0b0001


class Event(IntEnum):
    # 连接(1~49 上行, 50~99 下行)
    StartConnection = 1
    FinishConnection = 2
    ConnectionStarted = 50
    ConnectionFailed = 51
    ConnectionFinished = 52
    # 会话(100~149 上行, 150~199 下行)
    StartSession = 100
    CancelSession = 101
    FinishSession = 102
    SessionStarted = 150
    SessionCanceled = 151
    SessionFinished = 152
    SessionFailed = 153
    UsageResponse = 154
    # 通用(200~249 上行, 250~299 下行)
    TaskRequest = 200
    AudioMuted = 250
    # TTS 业务事件(350~399 下行)
    TTSSentenceStart = 350
    TTSSentenceEnd = 351
    TTSResponse = 352
    TTSEnded = 359
    # ASR 业务事件(450~499 下行)
    ASRResponse = 451


# 不携带 session_id 扩展的连接类事件
_CONNECTION_EVENTS = frozenset({
    Event.StartConnection, Event.FinishConnection,
    Event.ConnectionStarted, Event.ConnectionFailed, Event.ConnectionFinished,
})


@dataclass
class Message:
    type: int
    flag: int = MsgFlag.NoSeq
    serialization: int = Serialization.JSON
    compression: int = Compression.NONE
    event: int = 0
    session_id: str = ""
    sequence: int = 0
    payload: bytes = field(default=b"")

    def marshal(self) -> bytes:
        has_event = bool(self.flag & MsgFlag.WithEvent)
        out = bytearray()
        out.append((0b0001 << 4) | 0b0001)                       # v1, header size 4B
        out.append((self.type << 4) | self.flag)
        out.append((self.serialization << 4) | self.compression)
        out.append(0)
        if has_event:
            out += struct.pack(">i", self.event)
            if self.event not in _CONNECTION_EVENTS:
                sid = self.session_id.encode("utf-8")
                out += struct.pack(">I", len(sid)) + sid
        out += struct.pack(">I", len(self.payload))
        out += self.payload
        return bytes(out)

    @classmethod
    def parse(cls, data: bytes) -> "Message":
        if len(data) < 4:
            raise ValueError(f"协议帧过短: {len(data)} 字节")
        header_size = (data[0] & 0x0F) * 4
        msg_type = data[1] >> 4
        flag = data[1] & 0x0F
        serialization = data[2] >> 4
        compression = data[2] & 0x0F
        offset = header_size
        sequence, event, session_id = 0, 0, ""
        # 带正/负序号标记时, 头后先跟 4 字节序号(官方 demo 读取顺序: seq → event → session_id → payload)
        if flag in (MsgFlag.PositiveSeq, MsgFlag.NegativeSeq):
            sequence = struct.unpack(">i", data[offset:offset + 4])[0]
            offset += 4
        if flag & MsgFlag.WithEvent:
            event = struct.unpack(">i", data[offset:offset + 4])[0]
            offset += 4
            if event not in _CONNECTION_EVENTS:
                size = struct.unpack(">I", data[offset:offset + 4])[0]
                offset += 4
                if size:
                    session_id = data[offset:offset + size].decode("utf-8")
                    offset += size
        payload = b""
        if offset + 4 <= len(data):
            size = struct.unpack(">I", data[offset:offset + 4])[0]
            offset += 4
            payload = data[offset:offset + size]
        if compression == Compression.GZIP:
            payload = gzip.decompress(payload)
        return cls(
            type=msg_type, flag=flag, serialization=serialization,
            compression=compression, event=event, session_id=session_id,
            sequence=sequence, payload=payload,
        )


def encode_json_message(
    message_type: int, payload: dict, *, flag: int = MsgFlag.NoSeq,
    event: int = 0, session_id: str = "", compress: bool = False,
) -> bytes:
    """编码 JSON 业务消息(含可选事件头)"""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if compress:
        body = gzip.compress(body)
    return Message(
        type=message_type, flag=flag, serialization=Serialization.JSON,
        compression=Compression.GZIP if compress else Compression.NONE,
        event=event, session_id=session_id, payload=body,
    ).marshal()


def encode_audio(payload: bytes, *, last: bool = False) -> bytes:
    """编码音频帧(Raw 序列化, 无压缩; last=True 标记末包)"""
    flag = MsgFlag.LastNoSeq if last else MsgFlag.NoSeq
    return Message(
        type=MsgType.AudioOnlyClient, flag=flag,
        serialization=Serialization.Raw, compression=Compression.NONE,
        payload=payload,
    ).marshal()
