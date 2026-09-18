"""客服工具注册表

工具以装饰器方式注册, 统一暴露为 OpenAI function calling 格式; 
执行入口 execute_tool 统一做异常兜底, 保证 LLM 拿到的永远是可序列化的结果 
"""
import json
from dataclasses import dataclass
from typing import Callable, Dict, Any, List, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class ToolDefinition:
    name: str                       # 工具名(LLM 可见)
    description: str                # 工具描述(LLM 可见)
    parameters: Dict[str, Any]      # 参数 JSON Schema(LLM 可见)
    display: str                    # 前端展示名(如「正在查询订单」)
    handler: Callable[[Session, int, Dict[str, Any]], Any]  # (db, user_id, args) -> 可序列化结果


_TOOLS: Dict[str, ToolDefinition] = {}


def register_tool(name: str, description: str, parameters: Dict[str, Any], display: str):
    """工具注册装饰器"""
    def decorator(fn):
        _TOOLS[name] = ToolDefinition(name, description, parameters, display, fn)
        return fn
    return decorator


def get_tool(name: str) -> Optional[ToolDefinition]:
    return _TOOLS.get(name)


def get_openai_tools() -> List[dict]:
    """导出全部工具为 OpenAI function calling 格式"""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in _TOOLS.values()
    ]


def execute_tool(db: Session, user_id: int, name: str, args: Dict[str, Any]) -> dict:
    """执行工具并做统一异常兜底, 返回结构化结果(保证可 JSON 序列化)"""
    tool = get_tool(name)
    if not tool:
        return {"ok": False, "error": f"未知工具: {name}"}
    try:
        result = tool.handler(db, user_id, args)
        return {"ok": True, "data": result}
    except HTTPException as e:
        return {"ok": False, "error": e.detail}
    except Exception:
        return {"ok": False, "error": "工具执行失败, 请稍后重试"}


def dump_tool_result(result: dict) -> str:
    """工具结果序列化为喂回 LLM 的字符串"""
    return json.dumps(result, ensure_ascii=False, default=str)
