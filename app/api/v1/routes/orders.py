"""订单路由"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.services.order_service import OrderService
from app.api.v1.schemas.order import OrderCreateRequest
from app.api.v1.schemas.common import success_response
from app.models.user import User

router = APIRouter()


@router.get("")
async def list_orders(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    status: Optional[int] = Query(None, description="订单状态: 1=待支付, 2=已支付, 3=已取消"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询我的订单列表"""
    order_service = OrderService(db)
    data = await run_in_threadpool(
        order_service.list_orders,
        current_user.user_id,
        page,
        page_size,
        status,
    )
    return success_response(data=data)


@router.post("")
async def create_order(
    order_in: OrderCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """根据购物车选中商品创建待支付订单"""
    order_service = OrderService(db)
    data = await run_in_threadpool(
        order_service.create_order,
        current_user.user_id,
        order_in.product_ids,
    )
    return success_response(data=data, message="订单创建成功")


@router.get("/{order_id}")
async def get_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询订单详情"""
    order_service = OrderService(db)
    data = await run_in_threadpool(
        order_service.get_order,
        current_user.user_id,
        order_id,
    )
    return success_response(data=data)


@router.post("/{order_id}/pay")
async def pay_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """支付订单(余额扣款)"""
    order_service = OrderService(db)
    data = await run_in_threadpool(
        order_service.pay_order,
        current_user.user_id,
        order_id,
    )
    return success_response(data=data, message="支付成功")


@router.post("/{order_id}/cancel")
async def cancel_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """取消待支付订单(回补库存)"""
    order_service = OrderService(db)
    data = await run_in_threadpool(
        order_service.cancel_order,
        current_user.user_id,
        order_id,
    )
    return success_response(data=data, message="订单已取消")


@router.delete("/{order_id}")
async def delete_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除订单(仅已取消的订单)"""
    order_service = OrderService(db)
    await run_in_threadpool(
        order_service.delete_order,
        current_user.user_id,
        order_id,
    )
    return success_response(message="订单已删除")
