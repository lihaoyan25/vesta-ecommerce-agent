"""商品路由"""
from fastapi import APIRouter, Depends, Query
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_superuser
from app.services.product_service import ProductService
from app.api.v1.schemas.product import ProductCreate, ProductUpdate, ProductResponse
from app.api.v1.schemas.common import success_response
from app.models.user import User

router = APIRouter()


@router.get("")
async def get_products(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
):
    """获取商品列表(分页)"""
    product_service = ProductService(db)
    items, total = await run_in_threadpool(
        product_service.get_products, page, page_size, True
    )
    items_data = [ProductResponse.model_validate(p).model_dump() for p in items]
    return success_response(data={
        "items": items_data,
        "total": total,
        "page": page,
        "page_size": page_size,
    })


@router.get("/search")
async def search_products(
    keyword: str = Query(..., min_length=1, description="搜索关键词"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """搜索商品"""
    product_service = ProductService(db)
    items, total = await run_in_threadpool(
        product_service.search_products, keyword, page, page_size, True
    )
    items_data = [ProductResponse.model_validate(p).model_dump() for p in items]
    return success_response(data={
        "items": items_data,
        "total": total,
        "page": page,
        "page_size": page_size,
    })


@router.get("/{product_id}")
async def get_product_detail(
    product_id: int,
    db: Session = Depends(get_db),
):
    """获取商品详情"""
    product_service = ProductService(db)
    product = await run_in_threadpool(product_service.get_product, product_id, True)
    return success_response(data=ProductResponse.model_validate(product).model_dump())


@router.post("")
async def create_product(
    product_in: ProductCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_superuser),
):
    """创建商品(管理员)"""
    product_service = ProductService(db)
    product = await run_in_threadpool(
        product_service.create_product,
        product_in.name,
        product_in.price,
        product_in.stock,
        product_in.description,
        product_in.image_url,
    )
    return success_response(data=ProductResponse.model_validate(product).model_dump())


@router.put("/{product_id}")
async def update_product(
    product_id: int,
    product_in: ProductUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_superuser),
):
    """更新商品(管理员)"""
    product_service = ProductService(db)
    product = await run_in_threadpool(
        product_service.update_product,
        product_id,
        product_in.model_dump(exclude_unset=True),
    )
    return success_response(data=ProductResponse.model_validate(product).model_dump())


@router.delete("/{product_id}")
async def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_superuser),
):
    """删除商品(管理员, 软删除)"""
    product_service = ProductService(db)
    await run_in_threadpool(product_service.delete_product, product_id)
    return success_response(message="删除成功")
