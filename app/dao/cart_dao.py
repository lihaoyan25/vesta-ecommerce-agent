"""购物车数据访问层"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.cart import CartItem
from app.models.product import Product


class CartDAO:
    def get_by_user(self, db: Session, user_id: int) -> List[CartItem]:
        """获取用户的所有购物车项, 联查商品表, 带出商品名称、图片"""
        # join关联商品表, 这样CartItem对象会携带product子对象
        return db.query(CartItem)\
            .join(Product, CartItem.product_id == Product.product_id)\
            .filter(CartItem.user_id == user_id)\
            .all()

    def get_by_user_and_product(
        self, db: Session, user_id: int, product_id: int
    ) -> Optional[CartItem]:
        """获取用户指定商品的购物车项"""
        return db.query(CartItem).filter(
            CartItem.user_id == user_id,
            CartItem.product_id == product_id
        ).first()

    def clear_by_user(self, db: Session, user_id: int) -> None:
        """清空用户购物车(不提交, 由调用方控制事务)"""
        db.query(CartItem).filter(CartItem.user_id == user_id).delete()

    def delete_by_product(self, db: Session, user_id: int, product_id: int) -> None:
        """删除用户指定商品的购物车项(不提交, 由调用方控制事务)"""
        db.query(CartItem).filter(
            CartItem.user_id == user_id,
            CartItem.product_id == product_id
        ).delete()
