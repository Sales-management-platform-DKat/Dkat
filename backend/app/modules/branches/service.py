"""Branch management (FR-02).

- List / detail: OWNER sees every branch of the store, MANAGER/EMPLOYEE only assigned branches.
- Create / update / change status: OWNER only (checked in the router).
- branch_code is unique per store -> 409 DUPLICATE_BRANCH_CODE.
- A branch is never deleted; it is set INACTIVE. Refused (409 BRANCH_HAS_OPEN_PREORDERS) while it
  still has pre-orders WAITING_STOCK / READY / NOTIFIED.
- A new branch gets inventory rows (quantity 0) for every ACTIVE variant of the store.
"""
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.permissions import CurrentUser, get_accessible_branch_ids
from app.db.session import transaction
from app.modules.branches import repository
from app.modules.branches.models import Branch
from app.modules.branches.schemas import BranchCreatedOut, BranchIn, BranchOut
from app.utils.logger import get_logger

logger = get_logger("app.branches")


def _to_out(b: Branch) -> BranchOut:
    return BranchOut(
        id=b.branch_id,
        store_id=b.store_id,
        branch_code=b.branch_code,
        name=b.name,
        address=b.address,
        phone=b.phone,
        status=b.status,
        created_at=b.created_at,
    )


def _duplicate_code(code: str) -> AppError:
    return AppError(
        409,
        "DUPLICATE_BRANCH_CODE",
        f"Mã chi nhánh '{code}' đã tồn tại trong cửa hàng",
        [{"field": "branchCode", "message": "Branch code already exists in this store", "type": "duplicate"}],
    )


def _is_duplicate_key(exc: IntegrityError) -> bool:
    return getattr(getattr(exc, "orig", None), "args", [None])[0] == 1062


async def list_branches(db: AsyncSession, user: CurrentUser, status: str | None) -> list[BranchOut]:
    # OWNER: whole store (incl. INACTIVE). Others: their assigned ACTIVE branches only.
    ids = None if user.is_owner else get_accessible_branch_ids(user)
    return [_to_out(b) for b in await repository.list_branches(db, user.store_id, ids, status)]


async def get_branch(db: AsyncSession, user: CurrentUser, branch_id: int) -> BranchOut:
    # Access to branch_id was checked by require_branch_access; store_id filter is a second guard
    branch = await repository.get_branch(db, user.store_id, branch_id)
    if branch is None:
        raise AppError.not_found("Không tìm thấy chi nhánh")
    return _to_out(branch)


async def create_branch(db: AsyncSession, user: CurrentUser, body: BranchIn) -> BranchCreatedOut:
    if await repository.code_exists(db, user.store_id, body.branch_code):
        raise _duplicate_code(body.branch_code)
    try:
        async with transaction(db):
            branch = await repository.insert_branch(
                db,
                Branch(
                    store_id=user.store_id,
                    branch_code=body.branch_code,
                    name=body.name,
                    address=body.address,
                    phone=body.phone,
                ),
            )
            # Same transaction: the branch never exists without its inventory rows
            created = await repository.init_inventory_for_branch(db, user.store_id, branch.branch_id)
    except IntegrityError as exc:
        if _is_duplicate_key(exc):  # two requests with the same code at the same time
            raise _duplicate_code(body.branch_code) from exc
        raise
    logger.info("BRANCH_CREATED id=%s code=%s by user_id=%s inventory_rows=%s", branch.branch_id, branch.branch_code, user.id, created)
    return BranchCreatedOut(**_to_out(branch).model_dump(), inventory_rows_created=created)


async def update_branch(db: AsyncSession, user: CurrentUser, branch_id: int, body: BranchIn) -> BranchOut:
    branch = await repository.get_branch(db, user.store_id, branch_id)
    if branch is None:
        raise AppError.not_found("Không tìm thấy chi nhánh")
    if await repository.code_exists(db, user.store_id, body.branch_code, exclude_branch_id=branch_id):
        raise _duplicate_code(body.branch_code)
    try:
        async with transaction(db):
            branch.branch_code = body.branch_code
            branch.name = body.name
            branch.address = body.address
            branch.phone = body.phone
            branch = await repository.save_branch(db, branch)
    except IntegrityError as exc:
        if _is_duplicate_key(exc):
            raise _duplicate_code(body.branch_code) from exc
        raise
    logger.info("BRANCH_UPDATED id=%s by user_id=%s", branch_id, user.id)
    return _to_out(branch)


async def change_status(db: AsyncSession, user: CurrentUser, branch_id: int, status: str) -> BranchOut:
    async with transaction(db):
        # Lock the row: a pre-order created for this branch at the same moment waits for this decision
        branch = await repository.get_branch(db, user.store_id, branch_id, for_update=True)
        if branch is None:
            raise AppError.not_found("Không tìm thấy chi nhánh")
        if branch.status == status:
            return _to_out(branch)  # idempotent

        if status == "INACTIVE":
            open_count = await repository.count_open_preorders(db, branch_id)
            if open_count:
                raise AppError(
                    409,
                    "BRANCH_HAS_OPEN_PREORDERS",
                    f"Không thể ngừng hoạt động: chi nhánh còn {open_count} đơn đặt trước chưa hoàn tất",
                    {"openPreorders": open_count, "statuses": list(repository.OPEN_PREORDER_STATUSES)},
                )
        else:
            # Variants created while the branch was closed may have no inventory row yet
            await repository.init_inventory_for_branch(db, user.store_id, branch_id)

        branch.status = status
        branch = await repository.save_branch(db, branch)
    logger.info("BRANCH_STATUS id=%s status=%s by user_id=%s", branch_id, status, user.id)
    return _to_out(branch)
