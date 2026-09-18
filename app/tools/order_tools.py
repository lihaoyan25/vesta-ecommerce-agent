"""订单查询工具"""
from app.tools.registry import register_tool
from app.services.order_service import OrderService


@register_tool(
    name="query_my_orders",
    description="查询当前用户的订单列表(分页), 可按订单状态过滤 订单状态: 1=待支付, 2=已支付, 3=已取消",
    display="正在查询订单",
    parameters={
        "type": "object",
        "properties": {
            "status": {
                "type": "integer",
                "enum": [1, 2, 3],
                "description": "订单状态过滤: 1=待支付, 2=已支付, 3=已取消, 不传则查全部",
            },
            "page": {"type": "integer", "description": "页码, 默认 1"},
            "page_size": {"type": "integer", "description": "每页数量, 默认 10, 最大 50"},
        },
    },
)
def query_my_orders(db, user_id: int, args: dict) -> dict:
    service = OrderService(db)
    page = min(max(int(args.get("page", 1)), 1), 100)
    page_size = min(max(int(args.get("page_size", 10)), 1), 50)
    status = args.get("status")
    return service.list_orders(user_id, page, page_size, status)


@register_tool(
    name="query_order_detail",
    description="查询当前用户指定订单的详情(含商品明细), 仅能查询自己的订单",
    display="正在查询订单详情",
    parameters={
        "type": "object",
        "properties": {
            "order_id": {"type": "integer", "description": "订单 ID"},
        },
        "required": ["order_id"],
    },
)
def query_order_detail(db, user_id: int, args: dict) -> dict:
    order_id = int(args["order_id"])
    return OrderService(db).get_order(user_id, order_id)
