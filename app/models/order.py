""" 数据库订单模型 """
from sqlalchemy import Integer, String, DateTime, DECIMAL, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import List
from decimal import Decimal
from app.database import Base


class Order(Base):
    """订单主表"""
    __tablename__ = "orders"

    # 主键
    order_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="订单 ID")

    # 订单号(对外展示的唯一编号)
    order_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True, comment="订单号")

    # 外键 - 关联用户
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False, index=True, comment="用户 ID")

    # 订单金额
    total_amount: Mapped[Decimal] = mapped_column(DECIMAL(14, 2), nullable=False, comment="订单总金额")

    # 状态: 1=待支付, 2=已支付, 3=已取消
    status: Mapped[int] = mapped_column(Integer, default=1, nullable=False, index=True, comment="订单状态: 1=待支付, 2=已支付, 3=已取消")

    # 支付截止时间(超过则惰性取消)
    expire_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="支付截止时间")

    # 支付时间
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="支付时间")

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, comment="更新时间")

    # 关联关系 - 订单明细
    items: Mapped[List["OrderItem"]] = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"Order(order_id={self.order_id}, order_no={self.order_no}, status={self.status})"


class OrderItem(Base):
    """订单明细表(保存下单时的商品快照)"""
    __tablename__ = "order_items"

    # 主键
    item_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="订单项 ID")

    # 外键 - 关联订单
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.order_id"), nullable=False, index=True, comment="订单 ID")

    # 商品 ID(仅记录, 不做外键约束, 保证商品变更不影响历史订单)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="商品 ID")

    # 商品快照(下单时刻的商品信息, 不随商品表变化)
    product_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="商品名称快照")
    product_price: Mapped[Decimal] = mapped_column(DECIMAL(14, 2), nullable=False, comment="商品单价快照")
    image_url: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="商品图片快照")

    # 购买数量
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False, comment="购买数量")

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, comment="创建时间")

    # 关联关系
    order = relationship("Order", back_populates="items")

    def __repr__(self) -> str:
        return f"OrderItem(item_id={self.item_id}, order_id={self.order_id}, product_id={self.product_id}, quantity={self.quantity})"
