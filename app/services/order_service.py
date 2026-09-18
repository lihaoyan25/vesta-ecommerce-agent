"""订单业务服务"""
from typing import List, Optional
from decimal import Decimal
from datetime import datetime, timedelta
from uuid import uuid4
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.user import User
from app.dao.order_dao import OrderDAO
from app.dao.cart_dao import CartDAO

# 订单状态: 1=待支付, 2=已支付, 3=已取消
ORDER_STATUS_PENDING = 1
ORDER_STATUS_PAID = 2
ORDER_STATUS_CANCELLED = 3

# 待支付时长(分钟)
PAYMENT_TTL_MINUTES = 20


class OrderService:
    def __init__(self, db: Session):
        self.db = db
        self.order_dao = OrderDAO()
        self.cart_dao = CartDAO()

    def _generate_order_no(self) -> str:
        """生成订单号: 时间戳 + 8位随机串"""
        return f"{datetime.now():%Y%m%d%H%M%S}{uuid4().hex[:8].upper()}"

    def _lock_product(self, product_id: int) -> Optional[Product]:
        """加行锁查询商品(SELECT ... FOR UPDATE), 风格与DAO层一致"""
        return self.db.query(Product)\
            .filter(Product.product_id == product_id)\
            .with_for_update()\
            .populate_existing()\
            .first()

    def _restore_stock(self, order: Order) -> None:
        """取消订单时回补库存"""
        for item in order.items:
            product = self.db.query(Product)\
                .filter(Product.product_id == item.product_id)\
                .with_for_update()\
                .first()
            if product:
                product.stock += item.quantity

    def _lazy_cancel_expired(self, user_id: Optional[int] = None) -> None:
        """惰性取消: 将所有已超过支付截止时间的待支付订单置为已取消并回补库存"""
        expired_orders = self.order_dao.get_expired_pending(self.db, datetime.now(), user_id)
        if not expired_orders:
            return
        for order in expired_orders:
            self._restore_stock(order)
            order.status = ORDER_STATUS_CANCELLED
        self.db.commit()

    def _build_order_response(self, order: Order) -> dict:
        """构建订单响应数据"""
        items = []
        for item in order.items:
            items.append({
                "product_id": item.product_id,
                "product_name": item.product_name,
                "product_price": item.product_price,
                "image_url": item.image_url,
                "quantity": item.quantity,
                "subtotal": round(item.product_price * item.quantity, 2),
            })
        return {
            "order_id": order.order_id,
            "order_no": order.order_no,
            "total_amount": order.total_amount,
            "status": order.status,
            "expire_at": order.expire_at,
            "paid_at": order.paid_at,
            "created_at": order.created_at,
            "items": items,
        }

    def create_order(self, user_id: int, product_ids: List[int]) -> dict:
        """根据购物车选中商品创建待支付订单(下单锁库存防超卖)"""
        try:
            if not product_ids:
                raise HTTPException(status_code=400, detail="请先选择要结算的商品")

            # 1. 匹配购物车中的选中项
            cart_items = {
                item.product_id: item
                for item in self.cart_dao.get_by_user(self.db, user_id)
            }
            selected = []
            for pid in product_ids:
                item = cart_items.get(pid)
                if not item:
                    raise HTTPException(status_code=400, detail=f"购物车中不存在商品 {pid}")
                selected.append(item)

            # 2. 逐个锁定商品行, 二次校验库存并扣减(防超卖)
            total_amount = Decimal("0.00")
            order_items = []
            for item in selected:
                product = self._lock_product(item.product_id)
                if not product:
                    raise HTTPException(status_code=400, detail="商品不存在或已下架")
                if not product.is_active:
                    raise HTTPException(status_code=400, detail=f"商品【{product.name}】已下架")
                if product.stock < item.quantity:
                    raise HTTPException(status_code=400, detail=f"商品【{product.name}】库存不足")
                product.stock -= item.quantity
                total_amount += product.price * item.quantity
                order_items.append(OrderItem(
                    product_id=product.product_id,
                    product_name=product.name,
                    product_price=product.price,
                    image_url=product.image_url,
                    quantity=item.quantity,
                ))

            # 3. 创建订单(待支付, 20分钟内有效)
            order = Order(
                order_no=self._generate_order_no(),
                user_id=user_id,
                total_amount=round(total_amount, 2),
                status=ORDER_STATUS_PENDING,
                expire_at=datetime.now() + timedelta(minutes=PAYMENT_TTL_MINUTES),
            )
            order.items = order_items
            self.order_dao.add(self.db, order)

            # 4. 删除对应的购物车项
            for item in selected:
                self.cart_dao.delete_by_product(self.db, user_id, item.product_id)

            # 5. 一次性提交
            self.db.commit()
            self.db.refresh(order)
            return self._build_order_response(order)

        except Exception as e:
            self.db.rollback()
            raise e

    def list_orders(self, user_id: int, page: int, page_size: int, status: Optional[int] = None) -> dict:
        """查询用户订单列表(先惰性取消过期订单)"""
        self._lazy_cancel_expired(user_id)
        orders, total = self.order_dao.list_by_user(
            self.db, user_id, status,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return {
            "items": [self._build_order_response(o) for o in orders],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_order(self, user_id: int, order_id: int) -> dict:
        """查询订单详情"""
        self._lazy_cancel_expired(user_id)
        order = self.order_dao.get_user_order(self.db, user_id, order_id)
        if not order:
            raise HTTPException(status_code=404, detail="订单不存在")
        return self._build_order_response(order)

    def pay_order(self, user_id: int, order_id: int) -> dict:
        """支付订单(余额扣款, 锁用户行防并发透支)"""
        try:
            # 先惰性取消过期订单, 避免支付已超时订单
            self._lazy_cancel_expired(user_id)

            order = self.order_dao.get_user_order(self.db, user_id, order_id)
            if not order:
                raise HTTPException(status_code=404, detail="订单不存在")
            if order.status == ORDER_STATUS_CANCELLED:
                raise HTTPException(status_code=400, detail="订单已取消, 无法支付")
            if order.status == ORDER_STATUS_PAID:
                raise HTTPException(status_code=400, detail="订单已支付, 请勿重复支付")

            # 锁定用户行, 防止并发扣款透支
            user = self.db.query(User)\
                .filter(User.user_id == user_id)\
                .with_for_update()\
                .populate_existing()\
                .first()
            if user.balance < order.total_amount:
                raise HTTPException(status_code=400, detail="账户余额不足, 请先充值")

            user.balance -= order.total_amount
            order.status = ORDER_STATUS_PAID
            order.paid_at = datetime.now()

            self.db.commit()
            self.db.refresh(order)
            return self._build_order_response(order)

        except Exception as e:
            self.db.rollback()
            raise e

    def cancel_order(self, user_id: int, order_id: int) -> dict:
        """手动取消待支付订单(回补库存)"""
        try:
            self._lazy_cancel_expired(user_id)

            order = self.order_dao.get_user_order(self.db, user_id, order_id)
            if not order:
                raise HTTPException(status_code=404, detail="订单不存在")
            if order.status == ORDER_STATUS_PAID:
                raise HTTPException(status_code=400, detail="已支付订单不能取消")
            if order.status == ORDER_STATUS_CANCELLED:
                raise HTTPException(status_code=400, detail="订单已取消")

            self._restore_stock(order)
            order.status = ORDER_STATUS_CANCELLED

            self.db.commit()
            self.db.refresh(order)
            return self._build_order_response(order)

        except Exception as e:
            self.db.rollback()
            raise e

    def delete_order(self, user_id: int, order_id: int) -> None:
        """删除订单(仅允许删除已取消的订单)"""
        try:
            order = self.order_dao.get_user_order(self.db, user_id, order_id)
            if not order:
                raise HTTPException(status_code=404, detail="订单不存在")
            if order.status != ORDER_STATUS_CANCELLED:
                raise HTTPException(status_code=400, detail="仅已取消的订单可以删除")

            self.order_dao.delete(self.db, order)
            self.db.commit()

        except Exception as e:
            self.db.rollback()
            raise e
