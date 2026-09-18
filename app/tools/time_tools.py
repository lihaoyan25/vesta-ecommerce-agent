"""系统时间查询工具"""
from datetime import datetime

from app.tools.registry import register_tool

_WEEKDAY_TEXT = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


@register_tool(
    name="get_current_time",
    description="查询服务器当前系统时间(含星期), 用户询问现在几点、今天几号、星期几等时间问题时调用",
    display="正在查询系统时间",
    parameters={"type": "object", "properties": {}},
)
def get_current_time(db, user_id: int, args: dict) -> dict:
    now = datetime.now()
    return {
        "current_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "weekday": _WEEKDAY_TEXT[now.weekday()],
    }
