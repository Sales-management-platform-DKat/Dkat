from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.modules.products.category_schemas import Category, CategoryInput, CategoryNode, CategoryStatus
from app.modules.products.catalog_transaction import CatalogConflict as CategoryConflict
from app.modules.products.catalog_transaction import CatalogNotFound as CategoryNotFound

CATEGORY_COLUMNS = """
    category_id AS categoryId, parent_category_id AS parentCategoryId,
    name, description, status
"""


def list_categories(db: Connection, store_id: int, status: CategoryStatus | None) -> list[CategoryNode]:
    rows = db.execute(
        text(f"""
            SELECT {CATEGORY_COLUMNS} FROM categories
            WHERE store_id = :store AND (:status IS NULL OR status = :status)
            ORDER BY name, category_id
        """),
        {"store": store_id, "status": status},
    ).mappings()
    nodes = {row["categoryId"]: CategoryNode.model_validate(row) for row in rows}
    roots = []
    for node in nodes.values():
        parent = nodes.get(node.parentCategoryId)
        if parent is None:
            roots.append(node)
        else:
            parent.children.append(node)
    return roots


def lock_store(db: Connection, store_id: int) -> None:
    db.execute(text("SELECT store_id FROM stores WHERE store_id = :store FOR UPDATE"), {"store": store_id}).one()


def get_category(db: Connection, store_id: int, category_id: int) -> Category:
    row = db.execute(
        text(f"SELECT {CATEGORY_COLUMNS} FROM categories WHERE store_id = :store AND category_id = :id"),
        {"store": store_id, "id": category_id},
    ).mappings().one_or_none()
    if row is None:
        raise CategoryNotFound("Category not found")
    return Category.model_validate(row)


def save_category(
    db: Connection, store_id: int, data: CategoryInput, category_id: int | None = None
) -> Category:
    lock_store(db, store_id)
    if category_id is not None:
        get_category(db, store_id, category_id)

    parent_id = data.parentCategoryId
    visited = set()
    while parent_id is not None:
        if parent_id == category_id or parent_id in visited:
            raise CategoryConflict("Category hierarchy would contain a cycle")
        visited.add(parent_id)
        parent_id = get_category(db, store_id, parent_id).parentCategoryId

    params = {
        "store": store_id, "id": category_id, "parent": data.parentCategoryId,
        "name": data.name, "description": data.description,
    }
    duplicate = db.execute(
        text("""
            SELECT 1 FROM categories
            WHERE store_id = :store AND parent_category_id <=> :parent AND name = :name
              AND (:id IS NULL OR category_id <> :id)
            LIMIT 1
        """),
        params,
    ).first()
    if duplicate is not None:
        raise CategoryConflict("Category name already exists under this parent")

    if category_id is None:
        category_id = db.execute(
            text("""
                INSERT INTO categories (store_id, parent_category_id, name, description, status)
                VALUES (:store, :parent, :name, :description, 'ACTIVE')
            """),
            params,
        ).lastrowid
    else:
        db.execute(
            text("""
                UPDATE categories SET parent_category_id = :parent, name = :name,
                                      description = :description
                WHERE store_id = :store AND category_id = :id
            """),
            params,
        )
    return get_category(db, store_id, category_id)


def change_status(
    db: Connection, store_id: int, category_id: int, status: CategoryStatus
) -> Category:
    lock_store(db, store_id)
    get_category(db, store_id, category_id)
    params = {"store": store_id, "id": category_id, "status": status}
    if status == "INACTIVE" and db.execute(
        text("""
            SELECT 1 FROM products
            WHERE store_id = :store AND category_id = :id AND status = 'ACTIVE'
            LIMIT 1
        """),
        params,
    ).first() is not None:
        raise CategoryConflict("Category still contains active products")

    db.execute(
        text("UPDATE categories SET status = :status WHERE store_id = :store AND category_id = :id"),
        params,
    )
    return get_category(db, store_id, category_id)
