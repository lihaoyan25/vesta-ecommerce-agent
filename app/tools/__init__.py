"""客服工具层: 供 LLM function calling 调用的业务工具"""
from app.tools.registry import register_tool, get_tool, get_openai_tools, execute_tool, dump_tool_result

__all__ = ["register_tool", "get_tool", "get_openai_tools", "execute_tool", "dump_tool_result"]

# 导入工具模块以完成注册
from app.tools import order_tools, product_tools, cart_tools, time_tools  # noqa: E402,F401
