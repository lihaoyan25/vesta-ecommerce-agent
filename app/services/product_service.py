"""商品业务服务"""
from typing import List, Tuple
from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.product import Product
from app.dao.product_dao import ProductDAO

class ProductService:
    def __init__(self, db: Session):
        self.db = db
        self.product_dao = ProductDAO()

    def get_product(self, product_id: int, check_active: bool = True) -> Product:
        """获取商品详情"""
        product = self.product_dao.get_by_id(self.db, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="商品不存在")
        if check_active and not product.is_active:
            raise HTTPException(status_code=404, detail="商品不存在")
        return product

    def get_products(
        self,
        page: int = 1,
        page_size: int = 10,
        only_active: bool = True
    ) -> Tuple[List[Product], int]:
        """获取商品列表(分页)"""
        skip = (page - 1) * page_size
        products = self.product_dao.get_list(self.db, skip, page_size, only_active)
        total = self.product_dao.count(self.db, only_active)
        return products, total

    def search_products(
        self,
        keyword: str,
        page: int = 1,
        page_size: int = 10,
        only_active: bool = True
    ) -> Tuple[List[Product], int]:
        """搜索商品(分页)"""
        skip = (page - 1) * page_size
        products = self.product_dao.search(self.db, keyword, skip, page_size, only_active)
        total = self.product_dao.search_count(self.db, keyword, only_active)
        return products, total

    def create_product(
        self,
        name: str,
        price: Decimal,
        stock: int,
        description: str | None = None,
        image_url: str | None = None
    ) -> Product:
        """创建商品(管理员)"""
        product = Product(
            name=name,
            price=price,
            stock=stock,
            description=description,
            image_url=image_url,
            is_active=True
        )
        self.db.add(product)
        self.db.commit()
        self.db.refresh(product)
        return product

    def update_product(self, product_id: int, update_data: dict) -> Product:
        """更新商品(管理员)"""
        product = self.get_product(product_id, check_active=False)
        for key, value in update_data.items():
            if value is not None and hasattr(product, key):
                setattr(product, key, value)
        self.db.commit()
        self.db.refresh(product)
        return product

    def delete_product(self, product_id: int) -> None:
        """删除商品(软删除，管理员)"""
        product = self.get_product(product_id, check_active=False)
        product.is_active = False
        self.db.commit()

    def check_stock(self, product: Product, quantity: int) -> bool:
        """检查库存是否充足"""
        return product.stock >= quantity
