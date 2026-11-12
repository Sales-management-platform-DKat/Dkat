from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection

from app.modules.inventory.schemas import InventoryItem

LOW_STOCK_THRESHOLD = 5
AVAILABLE = "CAST(i.quantity AS SIGNED) - COALESCE(reservations.reserved, 0)"


def list_inventory(
    db: Connection, store_id: int, branch_ids: list[int], *,
    variant_id: int | None = None, keyword: str | None = None,
    low_stock: bool = False, limit: int = 50, offset: int = 0,
) -> list[InventoryItem]:
    if not branch_ids:
        return []

    term = (keyword or "").strip()
    pattern = "%" + term.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"
    rows = db.execute(
        text(f"""
            SELECT b.branch_id AS branchId, b.name AS branchName,
                   p.product_id AS productId, p.name AS productName,
                   v.variant_id AS variantId, v.variant_name AS variantName, v.sku,
                   i.quantity, COALESCE(reservations.reserved, 0) AS reserved,
                   {AVAILABLE} AS available, i.updated_at AS updatedAt
            FROM inventory AS i
            JOIN branches AS b ON b.branch_id = i.branch_id AND b.store_id = :store
            JOIN product_variants AS v ON v.variant_id = i.variant_id
            JOIN products AS p ON p.product_id = v.product_id AND p.store_id = :store
            LEFT JOIN (
                SELECT po.branch_id, item.variant_id, SUM(item.allocated_quantity) AS reserved
                FROM preorders AS po
                JOIN preorder_items AS item ON item.preorder_id = po.preorder_id
                WHERE po.branch_id IN :branches
                  AND po.status IN ('WAITING_STOCK', 'READY', 'NOTIFIED')
                  AND (:variant IS NULL OR item.variant_id = :variant)
                GROUP BY po.branch_id, item.variant_id
            ) AS reservations ON reservations.branch_id = i.branch_id
                             AND reservations.variant_id = i.variant_id
            WHERE i.branch_id IN :branches
              AND (:variant IS NULL OR i.variant_id = :variant)
              AND (:pattern IS NULL OR v.sku LIKE :pattern ESCAPE '!'
                   OR v.variant_name LIKE :pattern ESCAPE '!'
                   OR p.name LIKE :pattern ESCAPE '!')
              AND (NOT :low_stock OR ({AVAILABLE}) < :threshold)
            ORDER BY i.branch_id, i.variant_id
            LIMIT :limit OFFSET :offset
        """).bindparams(bindparam("branches", expanding=True)),
        {
            "store": store_id, "branches": branch_ids, "variant": variant_id,
            "pattern": pattern if term else None, "low_stock": low_stock,
            "threshold": LOW_STOCK_THRESHOLD, "limit": limit, "offset": offset,
        },
    ).mappings()
    return [InventoryItem.model_validate(row) for row in rows]
