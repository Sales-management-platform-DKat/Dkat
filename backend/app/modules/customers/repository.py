"""SQL queries for customers. Every query is limited to one store."""
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.customers.models import Customer


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def get_customer(db: AsyncSession, store_id: int, customer_id: int, *, for_update: bool = False) -> Customer | None:
    stmt = select(Customer).where(Customer.customer_id == customer_id, Customer.store_id == store_id)
    if for_update:
        stmt = stmt.with_for_update()
    return (await db.execute(stmt)).scalar_one_or_none()


async def find_by_phone(db: AsyncSession, store_id: int, phone: str) -> Customer | None:
    # uq_customers_store_phone (store_id, phone): index lookup
    stmt = select(Customer).where(Customer.store_id == store_id, Customer.phone == phone)
    return (await db.execute(stmt)).scalar_one_or_none()


async def search(
    db: AsyncSession, store_id: int, *, keyword: str | None, phone_digits: str | None, page: int, size: int
) -> tuple[list[Customer], int]:
    """Name contains `keyword`, or phone contains `phone_digits` (e.g. the last 4 digits).

    LIKE '%...%' cannot use an index; the scan is limited to one store via uq_customers_store_phone.
    """
    stmt = select(Customer).where(Customer.store_id == store_id)
    conditions = []
    if keyword:
        conditions.append(Customer.full_name.like(f"%{_escape_like(keyword)}%", escape="\\"))
    if phone_digits:
        conditions.append(Customer.phone.like(f"%{phone_digits}%"))
    if conditions:
        stmt = stmt.where(or_(*conditions))
    total = int((await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    page_stmt = stmt.order_by(Customer.full_name, Customer.customer_id).limit(size).offset((page - 1) * size)
    return list((await db.execute(page_stmt)).scalars()), total


async def insert(db: AsyncSession, customer: Customer) -> Customer:
    db.add(customer)
    await db.flush()
    await db.refresh(customer)  # created_at / updated_at
    return customer


async def save(db: AsyncSession, customer: Customer) -> Customer:
    await db.flush()
    await db.refresh(customer)
    return customer
