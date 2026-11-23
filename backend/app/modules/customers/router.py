"""Customer profiles API. Every route needs a login (401 without token).

GET  /customers/quick-search?phone   all staff; max 5 results, phone masked (NFR-08)
GET  /customers?keyword&page&size    all staff; keyword = name or part of the phone; phone masked
GET  /customers/{id}                 all staff; the ONLY read with full contact data; audited
POST /customers                      all staff (POS creates profiles); 409 DUPLICATE_CUSTOMER_PHONE + customerId
PUT  /customers/{id}                 OWNER / MANAGER
Customers belong to the store (not to a branch).
"""
from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import ROLE_MANAGER, ROLE_OWNER, CurrentUser, require_auth, require_role
from app.core.rate_limit import client_ip
from app.db.session import get_db
from app.modules.customers import service
from app.modules.customers.schemas import MAX_PAGE_SIZE, CustomerIn, CustomerOut, CustomerPageOut, CustomerSummaryOut
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
    """Tìm theo tên hoặc một phần SĐT (ví dụ 4 số cuối). Chỉ trả id, tên, SĐT đã che."""
    return ok(await service.list_customers(db, user, keyword=keyword, page=page, size=size))


# Declared before /{customer_id} so "quick-search" is not parsed as an id
@router.get("/quick-search", response_model=SuccessResponse[list[CustomerSummaryOut]], response_model_by_alias=True)
async def quick_search(
    phone: str = Query(min_length=1, max_length=20, description="Một phần SĐT, ít nhất 3 chữ số"),
    user: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """POS tìm nhanh: tối đa 5 khách {id, fullName, maskedPhone: 0912***678}. Khớp đúng SĐT xếp đầu."""
    return ok(await service.quick_search(db, user, phone))


@router.get("/{customer_id}", response_model=SuccessResponse[CustomerOut], response_model_by_alias=True)
async def get_customer(
    request: Request,
    customer_id: int = Path(gt=0),
    user: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Hồ sơ đầy đủ (SĐT, email, địa chỉ, ghi chú). Mỗi lần xem được ghi vào log truy cập."""
    return ok(await service.get_customer(db, user, customer_id, ip=client_ip(request)))


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
