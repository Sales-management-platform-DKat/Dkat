from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from app.modules.products.category_service import get_category, lock_store
from app.modules.products.catalog_transaction import CatalogConflict, CatalogNotFound
from app.modules.products.schemas import (
    Product, ProductCreate, ProductDetail, ProductInput, ProductRecord, ProductSort,
    ProductStatus, ProductVariant,
)
from app.modules.products.variant_service import list_variant_details

PRODUCT_ORDER = {
    "id": "p.product_id ASC",
    "-id": "p.product_id DESC",
    "name": "p.name ASC, p.product_id ASC",
    "-name": "p.name DESC, p.product_id ASC",
    "createdAt": "p.created_at ASC, p.product_id ASC",
    "-createdAt": "p.created_at DESC, p.product_id ASC",
}


def list_products(
    connection: Connection, store_id: int, limit: int, offset: int, *,
    keyword: str | None = None, category_id: int | None = None,
    status: ProductStatus = "ACTIVE", sort: ProductSort = "id",
) -> list[Product]:
    term = (keyword or "").strip()
    pattern = "%" + term.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"
    order = PRODUCT_ORDER[sort]
    rows = connection.execute(
        text(f"""
            SELECT p.product_id, p.category_id, p.product_code, p.name,
                   v.variant_id, v.sku, v.variant_name, v.price
            FROM (
                SELECT p.product_id, p.category_id, p.product_code, p.name, p.created_at
                FROM products AS p
                WHERE p.store_id = :store_id AND p.status = :status
                  AND (:category_id IS NULL OR p.category_id = :category_id)
                  AND (:pattern IS NULL
                    OR p.name LIKE :pattern ESCAPE '!'
                    OR p.product_code LIKE :pattern ESCAPE '!'
                    OR EXISTS (
                        SELECT 1 FROM product_variants AS matched
                        WHERE matched.product_id = p.product_id
                          AND matched.sku LIKE :pattern ESCAPE '!'
                    ))
                ORDER BY {order}
                LIMIT :limit OFFSET :offset
            ) AS p
            LEFT JOIN product_variants AS v
                ON v.product_id = p.product_id AND v.status = 'ACTIVE'
            ORDER BY {order}, v.variant_id
        """),
        {
            "store_id": store_id, "limit": limit, "offset": offset, "status": status,
            "category_id": category_id, "pattern": pattern if term else None,
        },
    ).mappings()

    products: dict[int, Product] = {}
    for row in rows:
        product = products.get(row["product_id"])
        if product is None:
            product = Product(
                product_id=row["product_id"],
                category_id=row["category_id"],
                product_code=row["product_code"],
                name=row["name"],
                variants=[],
            )
            products[product.product_id] = product
        if row["variant_id"] is not None:
            product.variants.append(ProductVariant.model_validate(row))
    return list(products.values())


def require_active_category(db: Connection, store_id: int, category_id: int) -> None:
    if get_category(db, store_id, category_id).status != "ACTIVE":
        raise CatalogConflict("Product category is inactive")


def get_product_record(db: Connection, store_id: int, product_id: int) -> ProductRecord:
    row = db.execute(
        text("""
            SELECT product_id AS productId, category_id AS categoryId,
                   product_code AS productCode, name, description, image_url AS imageUrl,
                   status, created_by AS createdBy
            FROM products WHERE store_id = :store AND product_id = :id
        """),
        {"store": store_id, "id": product_id},
    ).mappings().one_or_none()
    if row is None:
        raise CatalogNotFound("Product not found")
    return ProductRecord.model_validate(row)


def get_product_detail(db: Connection, store_id: int, product_id: int) -> ProductDetail:
    product = get_product_record(db, store_id, product_id)
    return ProductDetail(**product.model_dump(), variants=list_variant_details(db, store_id, product_id))


def create_product(db: Connection, store_id: int, user_id: int, data: ProductCreate) -> ProductRecord:
    lock_store(db, store_id)
    require_active_category(db, store_id, data.categoryId)
    try:
        result = db.execute(
            text("""
                INSERT INTO products
                    (store_id, category_id, product_code, name, description, image_url, status, created_by)
                VALUES (:store, :categoryId, :productCode, :name, :description, :imageUrl, 'ACTIVE', :user)
            """),
            {**data.model_dump(), "store": store_id, "user": user_id},
        )
    except IntegrityError as error:
        if getattr(error.orig, "args", ())[:1] == (1062,):
            raise CatalogConflict("Product code already exists in this store") from error
        raise
    return get_product_record(db, store_id, result.lastrowid)


def update_product(db: Connection, store_id: int, product_id: int, data: ProductInput) -> ProductRecord:
    lock_store(db, store_id)
    current = get_product_record(db, store_id, product_id)
    category = get_category(db, store_id, data.categoryId)
    if current.status == "ACTIVE" and category.status != "ACTIVE":
        raise CatalogConflict("Product category is inactive")
    db.execute(
        text("""
            UPDATE products SET category_id = :categoryId, name = :name,
                                description = :description, image_url = :imageUrl
            WHERE store_id = :store AND product_id = :id
        """),
        {**data.model_dump(), "store": store_id, "id": product_id},
    )
    return get_product_record(db, store_id, product_id)


def change_product_status(
    db: Connection, store_id: int, product_id: int, status: ProductStatus
) -> ProductRecord:
    lock_store(db, store_id)
    current = get_product_record(db, store_id, product_id)
    if status == "ACTIVE":
        require_active_category(db, store_id, current.categoryId)
    db.execute(
        text("UPDATE products SET status = :status WHERE store_id = :store AND product_id = :id"),
        {"store": store_id, "id": product_id, "status": status},
    )
    return get_product_record(db, store_id, product_id)
