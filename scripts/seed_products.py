"""商品种子数据初始化

读取 scripts/seed_data.json，向 products 表插入商品记录。
商品图片已在仓库 static/upload/ 中，随代码一起分发，本脚本只写数据库。

可重复执行：已存在的商品（按名称去重）自动跳过，不会产生重复数据。
"""
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models.product import Product

BASE_DIR = Path(__file__).parent
PROJECT_DIR = BASE_DIR.parent
SEED_FILE = BASE_DIR / "seed_data.json"
UPLOAD_DIR = PROJECT_DIR / "static" / "upload"


def seed_products():
    items = json.loads(SEED_FILE.read_text(encoding="utf-8"))

    db = SessionLocal()
    created, skipped = 0, 0
    try:
        # 幂等校验：按名称去重
        existing = {name for (name,) in db.query(Product.name).all()}
        for item in items:
            if item["name"] in existing:
                skipped += 1
                continue

            # 图片随仓库 static/upload/ 分发，校验存在后直接写 URL 字段
            image_url = None
            image_name = item.get("image")
            if image_name:
                if (UPLOAD_DIR / image_name).exists():
                    image_url = f"/static/upload/{image_name}"
                else:
                    print(f"警告: 图片缺失 static/upload/{image_name}，商品【{item['name']}】将无图")

            db.add(Product(
                name=item["name"],
                description=item.get("description"),
                price=Decimal(str(item["price"])),
                stock=int(item.get("stock", 0)),
                image_url=image_url,
                is_active=bool(item.get("is_active", True)),
            ))
            created += 1

        db.commit()
        print(f"商品种子数据初始化完成: 新增 {created} 条, 跳过 {skipped} 条(已存在)")
    finally:
        db.close()


if __name__ == "__main__":
    seed_products()
