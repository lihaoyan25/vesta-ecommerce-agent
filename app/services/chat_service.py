"""智能客服服务

职责: 
1. 会话管理(创建/列表/历史/删除/推荐卡片)
2. 对话编排: 组装上下文 → LLM 流式输出 → 工具调用循环(最多 N 轮)→ 消息落库

工具调用循环采用「惰性多轮」模式: 
LLM 返回 tool_calls → 执行工具(限定当前用户权限)→ 结果回填 → 继续生成, 
直到不再发起工具调用或达到轮数上限(超限时注入提示强制作答)
"""
import json
from pathlib import Path
from typing import AsyncIterator, Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool

from app.config import settings
from app.models.chat import ChatSession, ChatMessage
from app.services.llm_client import llm_client, LLMError
from app.tools import get_openai_tools, get_tool, execute_tool, dump_tool_result
from app.services.order_service import OrderService
from app.services.product_service import ProductService
from app.services.cart_service import CartService

# 送入 LLM 的历史消息条数上限(滑动窗口记忆)
HISTORY_LIMIT = 20
# 单次提问的工具调用轮数上限(防死循环)
MAX_TOOL_ROUNDS = 5

# 系统提示词外置文件(工具清单手写在提示词内, 便于随时调试, 改文件即生效)
SYSTEM_PROMPT_FILE = Path(__file__).resolve().parent.parent / "prompts" / "system_prompt.md"
_prompt_cache: Dict[str, Any] = {"mtime": None, "text": ""}


def load_system_prompt() -> str:
    """读取外置系统提示词; 按文件 mtime 缓存, 文件更新后自动重载(无需重启)"""
    if not SYSTEM_PROMPT_FILE.exists():
        raise RuntimeError(f"系统提示词文件缺失: {SYSTEM_PROMPT_FILE}")
    mtime = SYSTEM_PROMPT_FILE.stat().st_mtime
    if _prompt_cache["mtime"] != mtime:
        _prompt_cache["text"] = SYSTEM_PROMPT_FILE.read_text(encoding="utf-8").strip()
        _prompt_cache["mtime"] = mtime
    return _prompt_cache["text"]


ORDER_STATUS_TEXT = {1: "待支付", 2: "已支付", 3: "已取消"}


class ChatService:
    def __init__(self, db: Session):
        self.db = db

    # 会话管理(同步方法, 路由经线程池调用)

    def create_session(self, user_id: int) -> dict:
        """新建客服会话"""
        session = ChatSession(user_id=user_id)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return self._session_response(session)

    def list_sessions(self, user_id: int) -> List[dict]:
        """当前用户的会话列表"""
        sessions = (
            self.db.query(ChatSession)
            .filter(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc())
            .all()
        )
        return [self._session_response(s) for s in sessions]

    def get_messages(self, user_id: int, session_id: int) -> dict:
        """获取会话的完整消息历史"""
        session = self._get_owned_session(user_id, session_id)
        return {
            "session": self._session_response(session),
            "messages": [self._message_response(m) for m in session.messages],
        }

    def delete_session(self, user_id: int, session_id: int) -> None:
        """删除会话(级联删除消息)"""
        session = self._get_owned_session(user_id, session_id)
        self.db.delete(session)
        self.db.commit()

    def get_recommendations(self, user_id: int) -> dict:
        """推荐卡片: 最近订单 + 最新在售商品 + 购物车项, 供前端渲染后回发给客服"""
        orders_data = OrderService(self.db).list_orders(user_id, page=1, page_size=3)
        products, _ = ProductService(self.db).get_products(page=1, page_size=3, only_active=True)
        cart = CartService(self.db).get_cart(user_id)
        return {
            "orders": [
                {
                    "type": "order",
                    "id": o["order_id"],
                    "order_no": o["order_no"],
                    "status": o["status"],
                    "total_amount": o["total_amount"],
                }
                for o in orders_data["items"]
            ],
            "products": [
                {
                    "type": "product",
                    "id": p.product_id,
                    "name": p.name,
                    "price": p.price,
                    "image_url": p.image_url,
                }
                for p in products
            ],
            "carts": [
                {
                    "type": "cart",
                    "product_id": i["product_id"],
                    "name": i["product_name"],
                    "quantity": i["quantity"],
                }
                for i in cart.get("items", [])[:3]
            ],
        }

    # 对话编排(异步生成器, SSE 消费)

    async def chat_stream(
        self,
        user_id: int,
        session_id: int,
        content: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """处理一条用户消息, 流式产出事件: 
          meta  {session_id, user_message_id}
          delta {content}
          tool  {name, display}
          done  {message_id}
          error {message}
        """
        try:
            # 1. 处理卡片上下文并保存用户消息(同步 DB 操作进线程池)
            context_json = None
            if context:
                _, context_json = await run_in_threadpool(self._enrich_context, user_id, context)
            user_msg = await run_in_threadpool(
                self._save_user_message, user_id, session_id, content, context_json
            )
            yield {"type": "meta", "session_id": session_id, "user_message_id": user_msg.message_id}

            # 2. 组装 LLM 上下文(含滑动窗口历史)
            messages = await run_in_threadpool(self._build_llm_messages, session_id)

            # 3. 工具调用循环
            all_tools = get_openai_tools()
            rounds = 0
            emitted: List[str] = []  # 本次提问对用户可见的全部文本(跨工具轮次累计)

            while True:
                round_buf = ""
                tool_calls = None
                # 轮数达上限后不再提供工具, 强制模型基于已有信息作答
                use_tools = all_tools if rounds < MAX_TOOL_ROUNDS else None

                async for ev in llm_client.stream_chat(messages, use_tools):
                    if ev["type"] == "delta":
                        round_buf += ev["content"]
                        emitted.append(ev["content"])
                        yield ev
                    elif ev["type"] == "tool_calls":
                        tool_calls = ev["tool_calls"]

                if not tool_calls:
                    break

                # 记录 assistant 的工具调用消息(仅存在于本次上下文, 不落库)
                messages.append({
                    "role": "assistant",
                    "content": round_buf or None,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {"name": tc["name"], "arguments": tc["arguments"]},
                        }
                        for tc in tool_calls
                    ],
                })

                # 逐个执行工具并回填结果
                for tc in tool_calls:
                    tool_def = get_tool(tc["name"])
                    yield {
                        "type": "tool",
                        "name": tc["name"],
                        "display": tool_def.display if tool_def else tc["name"],
                    }
                    try:
                        args = json.loads(tc["arguments"] or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    result = await run_in_threadpool(execute_tool, self.db, user_id, tc["name"], args)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": dump_tool_result(result),
                    })

                rounds += 1
                if rounds >= MAX_TOOL_ROUNDS:
                    messages.append({
                        "role": "system",
                        "content": "工具调用次数已达上限, 请基于以上已获取的信息直接给出最终回答",
                    })

            # 4. 保存助手消息并收尾
            final_content = "".join(emitted).strip() or "抱歉, 客服暂时没有获取到有效回复, 请稍后重试"
            assistant_msg = await run_in_threadpool(
                self._save_assistant_message, session_id, final_content
            )
            yield {"type": "done", "message_id": assistant_msg.message_id}

        except LLMError as e:
            yield {"type": "error", "message": str(e)}
        except HTTPException as e:
            yield {"type": "error", "message": e.detail}
        except Exception:
            yield {"type": "error", "message": "客服服务异常, 请稍后再试"}

    # 内部方法

    def _get_owned_session(self, user_id: int, session_id: int) -> ChatSession:
        """获取当前用户的会话, 校验归属"""
        session = (
            self.db.query(ChatSession)
            .filter(ChatSession.session_id == session_id, ChatSession.user_id == user_id)
            .first()
        )
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
        return session

    def _save_user_message(
        self, user_id: int, session_id: int, content: str, context_json: Optional[str]
    ) -> ChatMessage:
        """保存用户消息; 首条消息自动生成会话标题"""
        session = self._get_owned_session(user_id, session_id)
        if session.title == "新会话":
            session.title = content[:20]
        msg = ChatMessage(session_id=session_id, role="user", content=content, context=context_json)
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def _save_assistant_message(self, session_id: int, content: str) -> ChatMessage:
        msg = ChatMessage(session_id=session_id, role="assistant", content=content)
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def _build_llm_messages(self, session_id: int) -> List[Dict[str, Any]]:
        """组装 LLM 上下文: system + 滑动窗口历史(含卡片快照文本)"""
        history = (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(HISTORY_LIMIT)
            .all()
        )
        history.reverse()

        messages: List[Dict[str, Any]] = [{"role": "system", "content": load_system_prompt()}]
        for m in history:
            content = m.content
            if m.role == "user" and m.context:
                try:
                    snapshot = json.loads(m.context)
                    content = f"{snapshot.get('text', '')}\n{content}"
                except json.JSONDecodeError:
                    pass
            messages.append({"role": m.role, "content": content})
        return messages

    def _enrich_context(self, user_id: int, context: Dict[str, Any]) -> Tuple[str, str]:
        """卡片上下文 → (注入文本, 存库快照JSON)

        快照在发送时刻生成并随消息落库, 历史重建时直接复用, 无需二次查询
        """
        ctx_type = context.get("type")
        ctx_id = int(context.get("id", 0))

        if ctx_type == "product":
            p = ProductService(self.db).get_product(ctx_id, check_active=False)
            text = (
                f"[用户发来商品卡片: 商品ID={p.product_id}, 名称={p.name}, "
                f"价格={p.price}元, 库存={p.stock}, {'在售中' if p.is_active else '已下架'}]"
            )
        elif ctx_type == "order":
            o = OrderService(self.db).get_order(user_id, ctx_id)
            status_text = ORDER_STATUS_TEXT.get(o["status"], "未知")
            text = (
                f"[用户发来订单卡片: 订单ID={o['order_id']}, 订单号={o['order_no']}, "
                f"状态={status_text}, 金额={o['total_amount']}元]"
            )
        else:
            raise HTTPException(status_code=400, detail="不支持的卡片类型")

        snapshot = json.dumps({"type": ctx_type, "id": ctx_id, "text": text}, ensure_ascii=False)
        return text, snapshot

    def _session_response(self, session: ChatSession) -> dict:
        return {
            "session_id": session.session_id,
            "title": session.title,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
        }

    def _message_response(self, msg: ChatMessage) -> dict:
        context = None
        if msg.context:
            try:
                context = json.loads(msg.context)
            except json.JSONDecodeError:
                context = None
        return {
            "message_id": msg.message_id,
            "role": msg.role,
            "content": msg.content,
            "context": context,
            "created_at": msg.created_at,
        }

