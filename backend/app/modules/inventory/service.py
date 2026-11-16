from fastapi import HTTPException
from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection

from app.core.permissions import Actor, require_branch_access
from app.modules.inventory.schemas import (
    MAX_STOCK_QUANTITY, ExportReason, InventoryItem, StockChangeResult, StockExportInput,
    StockImportInput, StockLineResult, StockMovementType, StocktakeInput,
)

LOW_STOCK_THRESHOLD = 5
AVAILABLE = "CAST(i.quantity AS SIGNED) - COALESCE(reservations.reserved, 0)"
OPEN_PREORDER_STATUSES = "'WAITING_STOCK', 'READY', 'NOTIFIED'"


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
                  AND po.status IN ({OPEN_PREORDER_STATUSES})
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


def check_variants(db: Connection, store_id: int, variant_ids: list[int]) -> None:
    found = db.execute(
        text("""
            SELECT v.variant_id
            FROM product_variants AS v
            JOIN products AS p ON p.product_id = v.product_id
            WHERE p.store_id = :store AND v.variant_id IN :variants
        """).bindparams(bindparam("variants", expanding=True)),
        {"store": store_id, "variants": variant_ids},
    ).scalars()
    missing = sorted(set(variant_ids) - set(found))
    if missing:
        raise HTTPException(404, {"code": "VARIANT_NOT_FOUND", "variantIds": missing})


def lock_inventory_rows(
    db: Connection, branch_id: int, variant_ids: list[int], *, create_missing: bool
) -> dict[int, tuple[int, int]]:
    rows = {}
    # Use the same ascending lock order for imports and exports.
    for variant_id in sorted(variant_ids):
        params = {"branch": branch_id, "variant": variant_id}
        if create_missing:
            db.execute(
                text("""
                    INSERT INTO inventory (branch_id, variant_id, quantity)
                    VALUES (:branch, :variant, 0)
                    ON DUPLICATE KEY UPDATE inventory_id = inventory_id
                """),
                params,
            )
        row = db.execute(
            text("""
                SELECT inventory_id, quantity FROM inventory
                WHERE branch_id = :branch AND variant_id = :variant
                FOR UPDATE
            """),
            params,
        ).one_or_none()
        if row is not None:
            rows[variant_id] = (row.inventory_id, row.quantity)
    return rows


def reserved_quantities(db: Connection, branch_id: int, variant_ids: list[int]) -> dict[int, int]:
    # Reservation writers must take the same inventory locks before changing allocations.
    rows = db.execute(
        text(f"""
            SELECT item.variant_id, SUM(item.allocated_quantity)
            FROM preorders AS po
            JOIN preorder_items AS item ON item.preorder_id = po.preorder_id
            WHERE po.branch_id = :branch AND po.status IN ({OPEN_PREORDER_STATUSES})
              AND item.variant_id IN :variants
            GROUP BY item.variant_id
        """).bindparams(bindparam("variants", expanding=True)),
        {"branch": branch_id, "variants": variant_ids},
    )
    return {variant_id: int(quantity) for variant_id, quantity in rows}


def check_export_stock(
    data: StockExportInput, rows: dict[int, tuple[int, int]], reserved_by_variant: dict[int, int]
) -> None:
    shortages = []
    for item in data.items:
        quantity = rows.get(item.variantId, (None, 0))[1]
        reserved = reserved_by_variant.get(item.variantId, 0)
        available = quantity - reserved
        if item.quantity > available:
            shortages.append({
                "variantId": item.variantId, "requested": item.quantity, "quantity": quantity,
                "reserved": reserved, "available": available,
            })
    if shortages:
        raise HTTPException(409, {"code": "INSUFFICIENT_STOCK", "items": shortages})


def record_movement(
    db: Connection, actor: Actor, *, variant_id: int, inventory_id: int,
    before: int, after: int, movement_type: StockMovementType, note: str | None,
    reason: ExportReason | None = None,
) -> StockLineResult:
    delta = after - before
    movement_id = None
    if delta:
        db.execute(
            text("UPDATE inventory SET quantity = :quantity WHERE inventory_id = :id"),
            {"quantity": after, "id": inventory_id},
        )
        movement_id = db.execute(
            text("""
                INSERT INTO inventory_movements
                    (inventory_id, movement_type, quantity_change, export_reason, note, created_by)
                VALUES (:inventory, :type, :delta, :reason, :note, :user)
            """),
            {
                "inventory": inventory_id, "type": movement_type, "delta": delta,
                "reason": reason, "note": note, "user": actor.user_id,
            },
        ).lastrowid
    return StockLineResult(
        variantId=variant_id, inventoryId=inventory_id, movementId=movement_id,
        quantityBefore=before, quantityChange=delta, quantityAfter=after,
    )


def record_stocktake(
    db: Connection, actor: Actor, data: StocktakeInput, rows: dict[int, tuple[int, int]],
    reserved_by_variant: dict[int, int],
) -> StockChangeResult:
    shortages = []
    for item in data.items:
        reserved = reserved_by_variant.get(item.variantId, 0)
        if item.countedQuantity < reserved:
            shortages.append({
                "variantId": item.variantId, "countedQuantity": item.countedQuantity,
                "quantity": rows[item.variantId][1], "reserved": reserved,
            })
    if shortages:
        raise HTTPException(409, {"code": "STOCK_BELOW_RESERVED", "items": shortages})

    results = []
    for item in data.items:
        inventory_id, before = rows[item.variantId]
        results.append(record_movement(
            db, actor, variant_id=item.variantId, inventory_id=inventory_id, before=before,
            after=item.countedQuantity, movement_type="ADJUSTMENT", note=data.note,
        ))
    return StockChangeResult(branchId=data.branchId, movementType="ADJUSTMENT", items=results)


def change_stock(
    db: Connection, actor: Actor, data: StockImportInput | StocktakeInput
) -> StockChangeResult:
    exporting = isinstance(data, StockExportInput)
    variant_ids = [item.variantId for item in data.items]
    require_branch_access(db, actor, data.branchId)
    check_variants(db, actor.store_id, variant_ids)
    rows = lock_inventory_rows(db, data.branchId, variant_ids, create_missing=not exporting)

    if isinstance(data, StocktakeInput):
        reserved = reserved_quantities(db, data.branchId, variant_ids)
        return record_stocktake(db, actor, data, rows, reserved)

    if isinstance(data, StockExportInput):
        check_export_stock(data, rows, reserved_quantities(db, data.branchId, variant_ids))
    movement_type = "EXPORT" if exporting else "IMPORT"
    reason = data.reason if isinstance(data, StockExportInput) else None
    results = []
    for item in data.items:
        inventory_id, before = rows[item.variantId]
        delta = -item.quantity if exporting else item.quantity
        after = before + delta
        if after > MAX_STOCK_QUANTITY:
            raise HTTPException(409, {"code": "STOCK_LIMIT_EXCEEDED", "variantId": item.variantId})
        results.append(record_movement(
            db, actor, variant_id=item.variantId, inventory_id=inventory_id, before=before,
            after=after, movement_type=movement_type, reason=reason, note=data.note,
        ))

    return StockChangeResult(branchId=data.branchId, movementType=movement_type, reason=reason, items=results)
