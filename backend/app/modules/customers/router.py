from typing import Annotated
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import bindparam, text

from app.core.exceptions import AppError
from app.core.audit import log_customer_access
from app.core.permissions import Actor, get_accessible_branch_ids, require_auth, require_owner_or_manager
from app.db.session import engine
from app.modules.customers.models import Customer  # register table metadata for fresh schemas
from app.modules.customers.schemas import CustomerCreate

router = APIRouter(prefix="/customers", tags=["customers"])
Reader = Annotated[Actor, Depends(require_auth)]


@router.get("")
def list_customers(request: Request, actor: Reader, q: str = Query(default="", max_length=200), limit: int = Query(default=100, ge=1, le=200)):
    term = q.strip()
    with engine.connect() as db:
        rows = db.execute(text("""
            SELECT c.customer_id AS customerId, c.full_name AS fullName, c.phone, c.email, c.address,
                   COALESCE(p.order_count, 0) AS orderCount, COALESCE(p.total_spent, 0) AS totalSpent
            FROM customers c LEFT JOIN (
                SELECT customer_id, COUNT(*) AS order_count, SUM(amount) AS total_spent FROM (
                    SELECT so.customer_id, so.total_amount AS amount FROM sales_orders so
                    JOIN branches sb ON sb.branch_id=so.branch_id AND sb.store_id=:store
                    WHERE so.status='PAID' AND so.customer_id IS NOT NULL
                      AND (:owner OR EXISTS (SELECT 1 FROM user_branches ub WHERE ub.user_id=:user AND ub.branch_id=so.branch_id))
                    UNION ALL
                    SELECT po.customer_id, po.total_amount FROM preorders po
                    JOIN branches pb ON pb.branch_id=po.branch_id AND pb.store_id=:store
                    WHERE po.status='FULFILLED' AND po.customer_id IS NOT NULL
                      AND (:owner OR EXISTS (SELECT 1 FROM user_branches ub WHERE ub.user_id=:user AND ub.branch_id=po.branch_id))
                ) purchases GROUP BY customer_id
            ) p ON p.customer_id=c.customer_id
            WHERE c.store_id=:store AND (:term='' OR c.full_name LIKE :like OR c.phone LIKE :like OR c.email LIKE :like)
            ORDER BY c.full_name LIMIT :limit
        """), {"store": actor.store_id, "owner": actor.role == "OWNER", "user": actor.user_id,
                "term": term, "like": f"%{term}%", "limit": limit}).mappings()
        result = [dict(row) for row in rows]
    log_customer_access(store_id=actor.store_id, user_id=actor.user_id, action="list", customer_ids=[row["customerId"] for row in result], ip=request.client.host if request.client else None)
    return result


@router.get("/{customer_id}/history")
def customer_history(customer_id: int, request: Request, actor: Reader, limit: int = Query(default=100, ge=1, le=200)):
    with engine.connect() as db:
        exists = db.execute(text("SELECT customer_id FROM customers WHERE customer_id=:id AND store_id=:store"), {"id": customer_id, "store": actor.store_id}).scalar_one_or_none()
        if exists is None:
            raise AppError.not_found("Customer not found.")
        branch_ids = None if actor.role == "OWNER" else get_accessible_branch_ids(db, actor)
        if branch_ids is not None and not branch_ids:
            return []
        clauses = " AND o.branch_id IN :branches" if branch_ids is not None else ""
        query = text(f"""
            SELECT o.sales_order_id AS id, 'SALE' AS type, o.order_code AS orderCode, o.branch_id AS branchId,
                   b.name AS branchName, o.created_at AS createdAt, o.status, o.total_amount AS totalAmount
            FROM sales_orders o JOIN branches b ON b.branch_id=o.branch_id AND b.store_id=:store
            WHERE o.customer_id=:customer {clauses}
            UNION ALL
            SELECT p.preorder_id, 'PREORDER', p.preorder_code, p.branch_id, b.name, p.created_at, p.status, p.total_amount
            FROM preorders p JOIN branches b ON b.branch_id=p.branch_id AND b.store_id=:store
            WHERE p.customer_id=:customer {clauses.replace('o.branch_id', 'p.branch_id')}
            ORDER BY createdAt DESC, id DESC LIMIT :limit
        """)
        if branch_ids is not None:
            query = query.bindparams(bindparam("branches", expanding=True))
        params = {"store": actor.store_id, "customer": customer_id, "limit": limit}
        if branch_ids is not None:
            params["branches"] = branch_ids
        result = [dict(row) for row in db.execute(query, params).mappings()]
    log_customer_access(store_id=actor.store_id, user_id=actor.user_id, action="purchase_history", customer_ids=[customer_id], ip=request.client.host if request.client else None)
    return result


@router.get("/quick-search")
def quick_search_customers(request: Request, actor: Reader, q: str = Query(default="", max_length=200), limit: int = Query(default=10, ge=1, le=50)):
    term = q.strip()
    if len(term) < 2:
        return []
    with engine.connect() as db:
        rows = db.execute(text("""
            SELECT customer_id AS customerId, full_name AS fullName, phone, email, address, note
            FROM customers WHERE store_id=:store AND (phone LIKE :term OR full_name LIKE :term OR email LIKE :term)
            ORDER BY full_name LIMIT :limit
        """), {"store": actor.store_id, "term": f"%{term}%", "limit": limit}).mappings()
        result = [dict(row) for row in rows]
    log_customer_access(store_id=actor.store_id, user_id=actor.user_id, action="quick_search", customer_ids=[row["customerId"] for row in result], ip=request.client.host if request.client else None)
    return result


@router.post("", status_code=201)
def create_customer(data: CustomerCreate, actor: Reader):
    with engine.begin() as db:
        if data.phone:
            existing = db.execute(text("""
                SELECT customer_id AS customerId, full_name AS fullName, phone, email, address, note
                FROM customers WHERE store_id=:store AND phone=:phone
            """), {"store": actor.store_id, "phone": data.phone}).mappings().one_or_none()
            if existing is not None:
                return dict(existing)
        result = db.execute(text("""
            INSERT INTO customers (store_id, full_name, phone, email, address, note)
            VALUES (:store, :name, :phone, :email, :address, :note)
        """), {"store": actor.store_id, "name": data.fullName, "phone": data.phone, "email": data.email, "address": data.address, "note": data.note})
        customer_id = result.lastrowid
    with engine.connect() as db:
        row = db.execute(text("SELECT customer_id AS customerId, full_name AS fullName, phone, email, address, note FROM customers WHERE customer_id=:id AND store_id=:store"), {"id":customer_id,"store":actor.store_id}).mappings().one_or_none()
    if row is None:
        raise AppError.not_found("Customer not found after save.")
    return dict(row)


@router.get("/{customer_id}")
def get_customer(customer_id: int, request: Request, actor: Reader):
    with engine.connect() as db:
        row = db.execute(text("""
            SELECT customer_id AS customerId, full_name AS fullName, phone, email, address, note
            FROM customers WHERE customer_id=:id AND store_id=:store
        """), {"id": customer_id, "store": actor.store_id}).mappings().one_or_none()
    if row is None:
        raise AppError.not_found("Customer not found.")
    log_customer_access(store_id=actor.store_id, user_id=actor.user_id, action="profile", customer_ids=[customer_id], ip=request.client.host if request.client else None)
    return dict(row)


@router.put("/{customer_id}")
def update_customer(customer_id: int, data: CustomerCreate, actor: Annotated[Actor, Depends(require_owner_or_manager)]):
    with engine.begin() as db:
        existing = db.execute(text("SELECT customer_id FROM customers WHERE customer_id=:id AND store_id=:store"), {"id": customer_id, "store": actor.store_id}).scalar_one_or_none()
        if existing is None:
            raise AppError.not_found("Customer not found.")
        if data.phone:
            duplicate = db.execute(text("SELECT customer_id FROM customers WHERE store_id=:store AND phone=:phone AND customer_id<>:id"), {"store": actor.store_id, "phone": data.phone, "id": customer_id}).scalar_one_or_none()
            if duplicate is not None:
                raise AppError.conflict("Phone number already belongs to another customer.")
        db.execute(text("""
            UPDATE customers SET full_name=:name, phone=:phone, email=:email, address=:address, note=:note
            WHERE customer_id=:id AND store_id=:store
        """), {"id": customer_id, "store": actor.store_id, "name": data.fullName, "phone": data.phone, "email": data.email, "address": data.address, "note": data.note})
        row = db.execute(text("""
            SELECT customer_id AS customerId, full_name AS fullName, phone, email, address, note
            FROM customers WHERE customer_id=:id AND store_id=:store
        """), {"id": customer_id, "store": actor.store_id}).mappings().one()
        return dict(row)
