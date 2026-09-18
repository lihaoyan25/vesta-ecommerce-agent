"""订单Schema"""
from typing import List, Optional
from pydantic import BaseModel, Field


class OrderCreateRequest(BaseModel):
    """创建订单: 购物车选中商品的 ID 列表"""
    product_ids: List[int] = Field(..., min_length=1, description="选中的商品 ID 列表")


class OrderStatusRequest(BaseModel):
    """订单列表查询: 可选状态过滤(1=待支付, 2=已支付, 3=已取消)"""
    pass
