"""Purchase history of a customer profile: POS sales orders + pre-orders.

- Branch scope: OWNER sees every branch; MANAGER/EMPLOYEE only orders of branches they are assigned
  to (list filtered, detail of another branch -> 403). Statistics use the same scope and dates.
- Statistics count completed purchases only: sales orders PAID and pre-orders FULFILLED.
- Order lines come from the snapshots stored on the order (name, SKU, price at the time of sale).
- Walk-in orders (customer_id NULL) are not linked to a profile: look them up in the order lists.
"""
import re
from datetime import date, datetime, time, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.permissions import CurrentUser, get_accessible_branch_ids
from app.modules.customers import history_repository, repository
from app.modules.customers.schemas import (
    CustomerOrderDetailOut,
    CustomerOrderHistoryOut,
    CustomerOrderOut,
    CustomerOrderStats,
    OrderBranchRef,
    OrderLineOut,
    OrderPaymentOut,
)

ORDER_KEY_PATTERN = re.compile(r"(SALE|PREORDER)-([1-9]\d{0,18})")


def order_key(order_type: str, order_id: int) -> str:
    return f"{order_type}-{order_id}"


def parse_order_key(key: str) -> tuple[str, int]:
    match = ORDER_KEY_PATTERN.fullmatch(key.strip().upper())
    if not match:
        raise AppError.validation(
            "Mã tham chiếu đơn phải có dạng SALE-<id> hoặc PREORDER-<id>",
            [{"field": "orderId", "message": "Expected SALE-<id> or PREORDER-<id>", "type": "format"}],
        )
    return match.group(1), int(match.group(2))


def _to_order(row) -> CustomerOrderOut:
    return CustomerOrderOut(
        key=order_key(row["type"], row["id"]),
        type=row["type"],
        id=row["id"],
        code=row["code"],
        created_at=row["created_at"],
        branch=OrderBranchRef(id=row["branch_id"], name=row["branch_name"]),
        total_amount=float(row["total_amount"]),
        status=row["status"],
        payment_status=row["payment_status"],
        # sorted here: MySQL orders an ENUM by declaration index, not alphabetically
        payment_methods=sorted(row["methods"].split(",")) if row["methods"] else [],
    )


async def _ensure_customer(db: AsyncSession, actor: CurrentUser, customer_id: int) -> None:
    if await repository.get_customer(db, actor.store_id, customer_id) is None:
        raise AppError.not_found("Không tìm thấy khách hàng")


def _scope(actor: CurrentUser) -> list[int] | None:
    return None if actor.is_owner else get_accessible_branch_ids(actor)


async def order_history(
    db: AsyncSession,
    actor: CurrentUser,
    customer_id: int,
    *,
    date_from: date | None,
    date_to: date | None,
    page: int,
    size: int,
) -> CustomerOrderHistoryOut:
    if date_from and date_to and date_from > date_to:
        raise AppError.validation(
            "Ngày bắt đầu phải trước hoặc bằng ngày kết thúc",
            [{"field": "from", "message": "from must be <= to", "type": "date_range"}],
        )
    await _ensure_customer(db, actor, customer_id)
    rows, total, count, spent = await history_repository.list_orders(
        db,
        customer_id,
        branch_ids=_scope(actor),
        date_from=datetime.combine(date_from, time.min) if date_from else None,
        # `to` is a whole day: everything before the next midnight
        date_to=datetime.combine(date_to + timedelta(days=1), time.min) if date_to else None,
        page=page,
        size=size,
    )
    return CustomerOrderHistoryOut(
        customer_id=customer_id,
        stats=CustomerOrderStats(purchase_count=count, total_spent=spent),
        items=[_to_order(r) for r in rows],
        page=page,
        size=size,
        total=total,
        total_pages=(total + size - 1) // size,
    )


async def order_detail(db: AsyncSession, actor: CurrentUser, customer_id: int, key: str) -> CustomerOrderDetailOut:
    order_type, order_id = parse_order_key(key)
    await _ensure_customer(db, actor, customer_id)
    row = await history_repository.get_order(db, customer_id, order_type, order_id)
    if row is None:  # unknown, or an order of another customer / a walk-in
        raise AppError.not_found("Không tìm thấy đơn hàng của khách này")
    scope = _scope(actor)
    if scope is not None and row["branch_id"] not in scope:
        raise AppError.forbidden("Bạn không được phân công tại chi nhánh của đơn hàng này")

    subtotal = discount = None
    if order_type == "SALE":
        subtotal, discount = await history_repository.sale_amounts(db, order_id)
    lines = await history_repository.order_lines(db, order_type, order_id)
    payments = await history_repository.order_payments(db, order_type, order_id)
    return CustomerOrderDetailOut(
        **_to_order(row).model_dump(),
        subtotal=float(subtotal) if subtotal is not None else None,
        discount_amount=float(discount) if discount is not None else None,
        lines=[
            OrderLineOut(
                product_name=line["product_name"],
                sku=line["sku"],
                unit_price=float(line["unit_price"]),
                quantity=line["quantity"],
                line_total=float(line["line_total"]),
            )
            for line in lines
        ],
        payments=[
            OrderPaymentOut(method=p["method"], amount=float(p["amount"]), status=p["status"], confirmed_at=p["confirmed_at"])
            for p in payments
        ],
    )
