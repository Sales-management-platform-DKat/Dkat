"""Customer profiles (optional: walk-in customers need none).

- One profile per phone per store: creating or changing to a phone that exists -> 409
  DUPLICATE_CUSTOMER_PHONE with the existing customerId, so the POS can reuse that profile.
- Search by name or by any part of the phone (e.g. the last 4 digits). Lists and quick search return
  only id, name and a masked phone (0912***678); the full profile comes from GET /customers/{id},
  and each of those views is written to the audit log (NFR-08).
- upsert_customer_by_phone(): for other modules (pre-orders, sales) inside their own transaction.
Logs never contain phone/email (personal data), only ids.
"""
import re

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_customer_view
from app.core.exceptions import AppError
from app.core.permissions import CurrentUser
from app.db.session import transaction
from app.modules.customers import repository
from app.modules.customers.models import Customer
from app.modules.customers.schemas import (
    CustomerIn,
    CustomerOut,
    CustomerPageOut,
    CustomerSummaryOut,
    mask_phone,
    normalize_phone,
)
from app.utils.logger import get_logger

logger = get_logger("app.customers")

MIN_PHONE_SEARCH_DIGITS = 3
QUICK_SEARCH_LIMIT = 5


def _to_out(c: Customer) -> CustomerOut:
    return CustomerOut(
        id=c.customer_id,
        full_name=c.full_name,
        phone=c.phone,
        email=c.email,
        address=c.address,
        note=c.note,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


def _to_summary(c: Customer) -> CustomerSummaryOut:
    return CustomerSummaryOut(id=c.customer_id, full_name=c.full_name, masked_phone=mask_phone(c.phone))


def _duplicate_phone(existing: Customer) -> AppError:
    return AppError(
        409,
        "DUPLICATE_CUSTOMER_PHONE",
        "Số điện thoại đã thuộc về một khách hàng khác",
        {"customerId": existing.customer_id, "fullName": existing.full_name},
    )


def _is_duplicate_key(exc: IntegrityError) -> bool:
    return getattr(getattr(exc, "orig", None), "args", [None])[0] == 1062


async def _raise_if_phone_taken(db: AsyncSession, store_id: int, phone: str | None, own_id: int | None = None) -> None:
    if phone is None:
        return
    existing = await repository.find_by_phone(db, store_id, phone)
    if existing is not None and existing.customer_id != own_id:
        raise _duplicate_phone(existing)


def phone_search_digits(keyword: str) -> str | None:
    """'0901 234', '.4567', '+84 901' -> digits to match inside stored phones; None if not a phone."""
    digits = re.sub(r"[\s().+-]", "", keyword)
    if not digits.isdigit() or len(digits) < MIN_PHONE_SEARCH_DIGITS:
        return None
    if keyword.strip().startswith("+84") or (digits.startswith("84") and len(digits) == 11):
        digits = "0" + digits[2:]  # stored phones use the domestic 0... form
    return digits


# --------------------------------------------------------------------------- API


async def create_customer(db: AsyncSession, actor: CurrentUser, body: CustomerIn) -> CustomerOut:
    await _raise_if_phone_taken(db, actor.store_id, body.phone)
    try:
        async with transaction(db):
            customer = await repository.insert(
                db,
                Customer(
                    store_id=actor.store_id,
                    full_name=body.full_name,
                    phone=body.phone,
                    email=body.email,
                    address=body.address,
                    note=body.note,
                ),
            )
    except IntegrityError as exc:
        # Same phone created at the same moment by another request: report the winner's id
        existing = await repository.find_by_phone(db, actor.store_id, body.phone) if body.phone else None
        if _is_duplicate_key(exc) and existing is not None:
            raise _duplicate_phone(existing) from exc
        raise
    logger.info("CUSTOMER_CREATED id=%s by user_id=%s", customer.customer_id, actor.id)
    return _to_out(customer)


async def list_customers(
    db: AsyncSession, actor: CurrentUser, *, keyword: str | None, page: int, size: int
) -> CustomerPageOut:
    keyword = keyword.strip() if keyword else None
    customers, total = await repository.search(
        db,
        actor.store_id,
        keyword=keyword,
        phone_digits=phone_search_digits(keyword) if keyword else None,
        page=page,
        size=size,
    )
    return CustomerPageOut(
        items=[_to_summary(c) for c in customers],
        page=page,
        size=size,
        total=total,
        total_pages=(total + size - 1) // size,
    )


async def quick_search(db: AsyncSession, actor: CurrentUser, phone: str) -> list[CustomerSummaryOut]:
    """POS lookup by (part of) a phone: at most QUICK_SEARCH_LIMIT results, phone masked."""
    digits = phone_search_digits(phone)
    if digits is None:
        raise AppError.validation(
            f"Nhập ít nhất {MIN_PHONE_SEARCH_DIGITS} chữ số của số điện thoại",
            [{"field": "phone", "message": f"At least {MIN_PHONE_SEARCH_DIGITS} digits", "type": "phone_digits"}],
        )
    customers = await repository.quick_search(db, actor.store_id, digits, QUICK_SEARCH_LIMIT)
    return [_to_summary(c) for c in customers]


async def get_customer(db: AsyncSession, actor: CurrentUser, customer_id: int, *, ip: str | None) -> CustomerOut:
    """The only read that returns the full profile; every successful view is audited (NFR-08)."""
    customer = await repository.get_customer(db, actor.store_id, customer_id)
    if customer is None:
        raise AppError.not_found("Không tìm thấy khách hàng")
    log_customer_view(user_id=actor.id, role=actor.role, store_id=actor.store_id, customer_id=customer_id, ip=ip)
    return _to_out(customer)


async def update_customer(db: AsyncSession, actor: CurrentUser, customer_id: int, body: CustomerIn) -> CustomerOut:
    try:
        async with transaction(db):
            customer = await repository.get_customer(db, actor.store_id, customer_id, for_update=True)
            if customer is None:
                raise AppError.not_found("Không tìm thấy khách hàng")
            await _raise_if_phone_taken(db, actor.store_id, body.phone, own_id=customer_id)
            customer.full_name = body.full_name
            customer.phone = body.phone
            customer.email = body.email
            customer.address = body.address
            customer.note = body.note
            customer = await repository.save(db, customer)
    except IntegrityError as exc:
        existing = await repository.find_by_phone(db, actor.store_id, body.phone) if body.phone else None
        if _is_duplicate_key(exc) and existing is not None:
            raise _duplicate_phone(existing) from exc
        raise
    logger.info("CUSTOMER_UPDATED id=%s by user_id=%s", customer_id, actor.id)
    return _to_out(customer)


# --------------------------------------------------------------------------- for other modules


async def upsert_customer_by_phone(
    db: AsyncSession,
    *,
    store_id: int,
    full_name: str,
    phone: str,
    email: str | None = None,
    address: str | None = None,
) -> int:
    """Return the id of the store's customer with this phone, creating the profile if needed.

    For pre-order / sales creation. Runs inside the CALLER's transaction (no commit here), so the
    profile is rolled back together with a failed order. An existing profile is never overwritten
    by data typed by a customer on the public form. Raises ValueError for an invalid phone.

        async with transaction(db):
            customer_id = await upsert_customer_by_phone(db, store_id=..., full_name=..., phone=...)
            ...insert the pre-order with customer_id...
    """
    phone = normalize_phone(phone)
    stmt = mysql_insert(Customer).values(
        store_id=store_id,
        full_name=full_name.strip()[:150],
        phone=phone,
        email=(email or "").strip() or None,
        address=(address or "").strip() or None,
    )
    # Atomic against concurrent orders with the same phone (uq_customers_store_phone); no-op update
    await db.execute(stmt.on_duplicate_key_update(customer_id=Customer.customer_id))
    return (
        await db.execute(select(Customer.customer_id).where(Customer.store_id == store_id, Customer.phone == phone))
    ).scalar_one()
