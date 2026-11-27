"""Public catalog for the customer website (FR-07). No login, rate limited per IP.

GET /public/branches?storeId=1            ACTIVE branches (id, name, address, phone)
GET /public/products?storeId=1&keyword=   ACTIVE products with ACTIVE variants; per ACTIVE branch only
                                          IN_STOCK / OUT_OF_STOCK (FR-07.5: never quantities, cost price,
                                          product codes or statuses). The pre-order form submits
                                          variantId + branchId, so both are exposed.

Available stock = inventory.quantity - allocated_quantity of open pre-orders (WAITING_STOCK / READY /
NOTIFIED) at that branch: the same rule the pre-order module uses to refuse in-stock pre-orders.
"""
import threading
import time
from collections import defaultdict, deque
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import bindparam, text
from sqlalchemy.exc import SQLAlchemyError
from app.core.db_errors import database_error

from app.db.session import engine

router = APIRouter(prefix="/public", tags=["public-catalog"])
StoreId = Annotated[int, Query(alias="storeId", gt=0, le=9223372036854775807)]

RATE_LIMIT_PER_MINUTE = 120
_hits: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


def _rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with _lock:
        hits = _hits[ip]
        while hits and hits[0] <= now - 60:
            hits.popleft()
        if len(hits) >= RATE_LIMIT_PER_MINUTE:
            raise HTTPException(429, {"code": "RATE_LIMIT_EXCEEDED", "message": "Quá nhiều yêu cầu, thử lại sau 1 phút"},
                                headers={"Retry-After": "60"})
        hits.append(now)


class PublicBranch(BaseModel):
    branchId: int
    name: str
    address: str
    phone: str | None


class BranchStock(BaseModel):
    branchId: int
    status: Literal["IN_STOCK", "OUT_OF_STOCK"]


class PublicVariant(BaseModel):
    variantId: int
    sku: str
    variantName: str
    price: Decimal
    stock: list[BranchStock]


class PublicProduct(BaseModel):
    productId: int
    name: str
    description: str | None
    imageUrl: str | None
    categoryName: str | None
    variants: list[PublicVariant]


def _branches(db, store_id: int) -> list[dict]:
    return [dict(r) for r in db.execute(text("""
        SELECT branch_id AS branchId, name, address, phone FROM branches
        WHERE store_id = :store AND status = 'ACTIVE' ORDER BY branch_id"""), {"store": store_id}).mappings()]


@router.get("/branches")
def public_branches(request: Request, store_id: StoreId) -> list[PublicBranch]:
    _rate_limit(request)
    try:
        with engine.connect() as db:
            return [PublicBranch(**b) for b in _branches(db, store_id)]
    except SQLAlchemyError as exc:
        raise database_error(exc) from None


@router.get("/products")
def public_products(
    request: Request, store_id: StoreId,
    keyword: Annotated[str | None, Query(max_length=100)] = None,
) -> list[PublicProduct]:
    _rate_limit(request)
    pattern = None
    if keyword and keyword.strip():
        pattern = "%" + keyword.strip().replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"
    try:
        with engine.connect() as db:
            branch_ids = [b["branchId"] for b in _branches(db, store_id)]
            rows = db.execute(text("""
                SELECT p.product_id, p.name, p.description, p.image_url, c.name AS category_name,
                       v.variant_id, v.sku, v.variant_name, v.price
                FROM products p
                JOIN product_variants v ON v.product_id = p.product_id AND v.status = 'ACTIVE'
                LEFT JOIN categories c ON c.category_id = p.category_id
                WHERE p.store_id = :store AND p.status = 'ACTIVE'
                  AND (c.category_id IS NULL OR c.status = 'ACTIVE')
                  AND (:pattern IS NULL OR p.name LIKE :pattern ESCAPE '!' OR v.variant_name LIKE :pattern ESCAPE '!')
                ORDER BY p.product_id, v.variant_id
                LIMIT 500"""), {"store": store_id, "pattern": pattern}).mappings().all()
            available: dict[tuple[int, int], int] = {}
            variant_ids = sorted({r["variant_id"] for r in rows})
            if variant_ids and branch_ids:
                stock = db.execute(text("""
                    SELECT i.branch_id, i.variant_id,
                           CAST(i.quantity AS SIGNED) - COALESCE((
                               SELECT SUM(item.allocated_quantity) FROM preorders po
                               JOIN preorder_items item ON item.preorder_id = po.preorder_id
                               WHERE po.branch_id = i.branch_id AND item.variant_id = i.variant_id
                                 AND po.status IN ('WAITING_STOCK', 'READY', 'NOTIFIED')), 0) AS available
                    FROM inventory i
                    WHERE i.branch_id IN :branches AND i.variant_id IN :variants""").bindparams(
                    bindparam("branches", expanding=True), bindparam("variants", expanding=True)),
                    {"branches": branch_ids, "variants": variant_ids}).mappings()
                available = {(s["branch_id"], s["variant_id"]): int(s["available"]) for s in stock}
    except SQLAlchemyError as exc:
        raise database_error(exc) from None

    products: dict[int, PublicProduct] = {}
    for r in rows:
        product = products.setdefault(r["product_id"], PublicProduct(
            productId=r["product_id"], name=r["name"], description=r["description"],
            imageUrl=r["image_url"], categoryName=r["category_name"], variants=[]))
        product.variants.append(PublicVariant(
            variantId=r["variant_id"], sku=r["sku"], variantName=r["variant_name"], price=r["price"],
            stock=[BranchStock(branchId=b, status="IN_STOCK" if available.get((b, r["variant_id"]), 0) > 0 else "OUT_OF_STOCK")
                   for b in branch_ids]))
    return list(products.values())
