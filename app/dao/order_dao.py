"""订单数据访问层"""
from typing import List, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.order import Order, OrderItem


class OrderDAO:
    def get_user_order(self, db: Session, user_id: int, order_id: int) -> Optional[Order]:
        """获取用户指定订单(校验归属)"""
        return db.query(Order).filter(
            Order.order_id == order_id,
            Order.user_id == user_id
        ).first()

    def list_by_user(
        self, db: Session, user_id: int, status: Optional[int], offset: int, limit: int
    ) -> Tuple[List[Order], int]:
        """分页获取用户订单列表, 返回(订单列表, 总数)"""
        query = db.query(Order).filter(Order.user_id == user_id)
        if status is not None:
            query = query.filter(Order.status == status)
        total = query.count()
        orders = query.order_by(Order.created_at.desc()).offset(offset).limit(limit).all()
        return orders, total

    def get_expired_pending(self, db: Session, now: datetime, user_id: Optional[int] = None) -> List[Order]:
        """获取已过期的待支付订单(用于惰性取消)"""
        query = db.query(Order).filter(
            Order.status == 1,
            Order.expire_at <= now
        )
        if user_id is not None:
            query = query.filter(Order.user_id == user_id)
        return query.all()

    def add(self, db: Session, order: Order) -> None:
        """新增订单(不提交, 由调用方控制事务)"""
        db.add(order)

    def delete(self, db: Session, order: Order) -> None:
        """删除订单(含明细级联, 不提交, 由调用方控制事务)"""
        db.delete(order)
