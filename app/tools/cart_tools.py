"""购物车查询/修改工具"""
from app.tools.registry import register_tool
from app.services.cart_service import CartService


@register_tool(
    name="query_my_cart",
    description="查询当前用户的购物车(商品, 数量, 小计, 合计)",
    display="正在查询购物车",
    parameters={"type": "object", "properties": {}},
)
def query_my_cart(db, user_id: int, args: dict) -> dict:
    return CartService(db).get_cart(user_id)


@register_tool(
    name="add_to_cart",
    description="把指定商品加入当前用户购物车(可指定数量, 默认 1)",
    display="正在添加购物车",
    parameters={
        "type": "object",
        "properties": {
            "product_id": {"type": "integer", "description": "商品 ID"},
            "quantity": {"type": "integer", "description": "数量, 默认 1"},
        },
        "required": ["product_id"],
    },
)
def add_to_cart(db, user_id: int, args: dict) -> dict:
    quantity = max(int(args.get("quantity", 1)), 1)
    return CartService(db).add_item(user_id, int(args["product_id"]), quantity)


@register_tool(
    name="update_cart_quantity",
    description="修改当前用户购物车中某商品的数量",
    display="正在修改购物车数量",
    parameters={
        "type": "object",
        "properties": {
            "product_id": {"type": "integer", "description": "商品 ID"},
            "quantity": {"type": "integer", "description": "新数量(至少 1)"},
        },
        "required": ["product_id", "quantity"],
    },
)
def update_cart_quantity(db, user_id: int, args: dict) -> dict:
    quantity = max(int(args["quantity"]), 1)
    return CartService(db).update_item_quantity(user_id, int(args["product_id"]), quantity)


@register_tool(
    name="remove_from_cart",
    description="把指定商品从当前用户购物车中移除",
    display="正在移除购物车商品",
    parameters={
        "type": "object",
        "properties": {
            "product_id": {"type": "integer", "description": "商品 ID"},
        },
        "required": ["product_id"],
    },
)
def remove_from_cart(db, user_id: int, args: dict) -> dict:
    return CartService(db).remove_item(user_id, int(args["product_id"]))
