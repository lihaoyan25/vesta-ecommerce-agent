"""智能客服路由(SSE 流式)"""
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.api.deps import get_current_user
from app.services.chat_service import ChatService
from app.api.v1.schemas.chat import ChatSendRequest
from app.api.v1.schemas.common import success_response
from app.models.user import User

router = APIRouter()


def _ensure_llm_enabled():
    """客服功能依赖 LLM 配置, 未配置时统一拒绝"""
    if not settings.LLM_ENABLED:
        raise HTTPException(status_code=503, detail="智能客服功能未启用, 请先配置 DEEPSEEK_API_KEY")


@router.post("/sessions")
async def create_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """新建客服会话"""
    _ensure_llm_enabled()
    chat_service = ChatService(db)
    data = await run_in_threadpool(chat_service.create_session, current_user.user_id)
    return success_response(data=data)


@router.get("/sessions")
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """当前用户的会话列表"""
    _ensure_llm_enabled()
    chat_service = ChatService(db)
    data = await run_in_threadpool(chat_service.list_sessions, current_user.user_id)
    return success_response(data=data)


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取会话消息历史"""
    _ensure_llm_enabled()
    chat_service = ChatService(db)
    data = await run_in_threadpool(chat_service.get_messages, current_user.user_id, session_id)
    return success_response(data=data)


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除会话"""
    _ensure_llm_enabled()
    chat_service = ChatService(db)
    await run_in_threadpool(chat_service.delete_session, current_user.user_id, session_id)
    return success_response(message="会话已删除")


@router.get("/recommendations")
async def get_recommendations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """推荐卡片(最近订单 + 在售商品), 前端渲染后可随消息回发给客服"""
    _ensure_llm_enabled()
    chat_service = ChatService(db)
    data = await run_in_threadpool(chat_service.get_recommendations, current_user.user_id)
    return success_response(data=data)


@router.post("/sessions/{session_id}/messages/stream")
async def stream_message(
    session_id: int,
    body: ChatSendRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """发送消息并流式接收回复(SSE)

    事件流格式(text/event-stream, 每事件一行 data JSON): 
      data: {"type": "meta",  "session_id": 1, "user_message_id": 10}
      data: {"type": "delta", "content": "部分回复文本"}
      data: {"type": "tool",  "name": "query_my_orders", "display": "正在查询订单"}
      data: {"type": "done",  "message_id": 11}
      data: {"type": "error", "message": "错误描述"}
    """
    _ensure_llm_enabled()
    chat_service = ChatService(db)

    async def event_generator():
        try:
            async for event in chat_service.chat_stream(
                current_user.user_id,
                session_id,
                body.content,
                body.context.model_dump() if body.context else None,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
        except Exception:
            yield f"data: {json.dumps({'type': 'error', 'message': '客服服务异常, 请稍后再试'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Nginx 反代时关闭缓冲, 保证流式即时到达
        },
    )
