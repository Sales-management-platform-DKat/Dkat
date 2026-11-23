"""Customer profiles API.

GET  /customers?keyword&page&size   all staff (POS lookup); keyword = name or part of the phone
GET  /customers/{id}                all staff
POST /customers                     all staff (POS creates profiles); 409 DUPLICATE_CUSTOMER_PHONE + customerId
PUT  /customers/{id}                OWNER / MANAGER
Customers belong to the store (not to a branch).
"""
from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import ROLE_MANAGER, ROLE_OWNER, CurrentUser, require_auth, require_role
from app.db.session import get_db
from app.modules.customers import service
from app.modules.customers.schemas import MAX_PAGE_SIZE, CustomerIn, CustomerOut, CustomerPageOut
from app.utils.response import SuccessResponse, ok

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("", response_model=SuccessResponse[CustomerPageOut], response_model_by_alias=True)
async def list_customers(
    keyword: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    user: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Tìm theo tên hoặc một phần SĐT (ví dụ 4 số cuối)."""
    return ok(await service.list_customers(db, user, keyword=keyword, page=page, size=size))


@router.get("/{customer_id}", response_model=SuccessResponse[CustomerOut], response_model_by_alias=True)
async def get_customer(
    customer_id: int = Path(gt=0), user: CurrentUser = Depends(require_auth), db: AsyncSession = Depends(get_db)
):
    return ok(await service.get_customer(db, user, customer_id))


@router.post("", status_code=201, response_model=SuccessResponse[CustomerOut], response_model_by_alias=True)
async def create_customer(body: CustomerIn, user: CurrentUser = Depends(require_auth), db: AsyncSession = Depends(get_db)):
    """fullName bắt buộc; SĐT 10 số bắt đầu bằng 0; trùng SĐT -> 409 kèm customerId của khách cũ."""
    return ok(await service.create_customer(db, user, body))


@router.put(
    "/{customer_id}",
    dependencies=[Depends(require_role(ROLE_OWNER, ROLE_MANAGER))],
    response_model=SuccessResponse[CustomerOut],
    response_model_by_alias=True,
)
async def update_customer(
    body: CustomerIn,
    customer_id: int = Path(gt=0),
    user: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Thay toàn bộ thông tin khách (OWNER/MANAGER). Đổi sang SĐT đã có -> 409."""
    return ok(await service.update_customer(db, user, customer_id, body))
