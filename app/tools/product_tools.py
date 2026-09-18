"""商品查询工具(Text2SQL 统一查询)"""
from app.tools.registry import register_tool
from app.tools.sql_query import run_product_query


@register_tool(
    name="search_products",
    description="商品数据统一查询(内部自动生成 SQL): 支持按名称关键词、价格区间、库存、上架时间等任意条件组合筛选、排序、统计, 也可用商品 ID 精确查询商品详情",
    display="正在查询商品",
    parameters={
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "用自然语言完整描述要查询的商品条件, 例如: 价格低于3000且有库存的商品按价格升序; 或: 商品ID为3的详情",
            },
        },
        "required": ["question"],
    },
)
def search_products(db, user_id: int, args: dict) -> dict:
    question = str(args.get("question", ""))
    return run_product_query(db, question)
