from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text

from app.core.exceptions import AppError
from app.core.permissions import Actor, require_auth
from app.db.session import engine
from app.modules.customers.models import Customer  # register table metadata for fresh schemas
from app.modules.customers.schemas import CustomerCreate

router = APIRouter(prefix="/customers", tags=["customers"])
Reader = Annotated[Actor, Depends(require_auth)]


@router.get("/quick-search")
def quick_search_customers(actor: Reader, q: str = Query(default="", max_length=200), limit: int = Query(default=10, ge=1, le=50)):
    term = q.strip()
    if len(term) < 2:
        return []
    with engine.connect() as db:
        rows = db.execute(text("""
            SELECT customer_id AS customerId, full_name AS fullName, phone, email, address
            FROM customers WHERE store_id=:store AND (phone LIKE :term OR full_name LIKE :term)
            ORDER BY full_name LIMIT :limit
        """), {"store": actor.store_id, "term": f"%{term}%", "limit": limit}).mappings()
        return [dict(row) for row in rows]


@router.post("", status_code=201)
def create_customer(data: CustomerCreate, actor: Reader):
    with engine.begin() as db:
        if data.phone:
            existing = db.execute(text("""
                SELECT customer_id AS customerId, full_name AS fullName, phone, email, address
                FROM customers WHERE store_id=:store AND phone=:phone
            """), {"store": actor.store_id, "phone": data.phone}).mappings().one_or_none()
            if existing is not None:
                return dict(existing)
        result = db.execute(text("""
            INSERT INTO customers (store_id, full_name, phone, email, address)
            VALUES (:store, :name, :phone, :email, :address)
        """), {"store": actor.store_id, "name": data.fullName, "phone": data.phone, "email": data.email, "address": data.address})
        customer_id = result.lastrowid
    with engine.connect() as db:
        row = db.execute(text("SELECT customer_id AS customerId, full_name AS fullName, phone, email, address FROM customers WHERE customer_id=:id AND store_id=:store"), {"id":customer_id,"store":actor.store_id}).mappings().one_or_none()
    if row is None:
        raise AppError.not_found("Customer not found after save.")
    return dict(row)
