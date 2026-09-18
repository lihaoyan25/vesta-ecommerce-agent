""" 数据库客服会话模型 """
from sqlalchemy import Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import List
from app.database import Base


class ChatSession(Base):
    """客服会话"""
    __tablename__ = "chat_sessions"

    # 主键
    session_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="会话 ID")

    # 外键 - 关联用户
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False, index=True, comment="用户 ID")

    # 会话标题(默认取首条消息截断)
    title: Mapped[str] = mapped_column(String(100), default="新会话", nullable=False, comment="会话标题")

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, comment="更新时间")

    # 关联关系 - 会话消息
    messages: Mapped[List["ChatMessage"]] = relationship(
        "ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at"
    )

    def __repr__(self) -> str:
        return f"ChatSession(session_id={self.session_id}, user_id={self.user_id}, title={self.title})"


class ChatMessage(Base):
    """客服消息"""
    __tablename__ = "chat_messages"

    # 主键
    message_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="消息 ID")

    # 外键 - 关联会话
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.session_id"), nullable=False, index=True, comment="会话 ID")

    # 角色: user=用户, assistant=客服
    role: Mapped[str] = mapped_column(String(20), nullable=False, comment="角色: user / assistant")

    # 消息内容
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="消息内容")

    # 卡片上下文快照(JSON 字符串: {type, id, text}, 用户发送商品/订单卡片时记录)
    context: Mapped[str | None] = mapped_column(Text, nullable=True, comment="卡片上下文快照 JSON")

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, comment="创建时间")

    # 关联关系
    session = relationship("ChatSession", back_populates="messages")

    def __repr__(self) -> str:
        return f"ChatMessage(message_id={self.message_id}, session_id={self.session_id}, role={self.role})"
