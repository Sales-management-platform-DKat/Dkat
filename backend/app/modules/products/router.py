from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import ROLE_OWNER, CurrentUser, require_role
from app.db.session import get_db
from app.modules.products import service
from app.modules.products.schemas import ProductCreateIn, ProductOut
from app.utils.response import SuccessResponse, ok

router = APIRouter(prefix="/products", tags=["products"])


@router.post("", status_code=201, response_model=SuccessResponse[ProductOut], response_model_by_alias=True)
async def create_product(
    body: ProductCreateIn,
    user: CurrentUser = Depends(require_role(ROLE_OWNER)),
    db: AsyncSession = Depends(get_db),
):
    """Tạo sản phẩm (chỉ OWNER). MANAGER/EMPLOYEE -> 403 FORBIDDEN. 409 nếu trùng productCode."""
    return ok(await service.create_product(db, user, body))
