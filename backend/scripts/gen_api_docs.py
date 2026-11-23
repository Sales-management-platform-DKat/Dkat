"""Generate docs/api-endpoints.md and docs/openapi.json from the REAL app (no hand-written list).

Run from backend/:  python -m scripts.gen_api_docs          (rewrites the two files)
                    python -m scripts.gen_api_docs --check  (exit 1 if the files are out of date)
Access rules are read from the route dependencies themselves (require_auth / require_role /
require_branch_access), so the table cannot drift from what the server enforces.
"""
import argparse
import json
import sys
from pathlib import Path

from fastapi.routing import APIRoute

from app.core.config import settings
from app.core.permissions import require_auth
from app.main import create_app

DOCS = Path(__file__).resolve().parents[2] / "docs"
ROLE_ORDER = ("OWNER", "MANAGER", "EMPLOYEE")
GROUP_TITLES = {
    "health": "Hệ thống", "auth": "Xác thực", "branches": "Chi nhánh", "users": "Tài khoản nội bộ",
    "customers": "Khách hàng", "products": "Sản phẩm", "inventory": "Tồn kho", "reports": "Báo cáo",
    "notifications": "Thông báo", "public": "Công khai (không đăng nhập)",
}


def iter_routes(routes, prefix: str = ""):
    """(full path, APIRoute). FastAPI >= 0.16x keeps included routers as wrappers
    (`original_router` + `include_context.prefix`) instead of copying the routes into app.routes."""
    for r in routes:
        if isinstance(r, APIRoute):
            yield prefix + r.path, r
        elif hasattr(r, "original_router"):
            ctx = getattr(r, "include_context", None)
            yield from iter_routes(r.original_router.routes, prefix + (getattr(ctx, "prefix", "") or ""))


def _calls(dependant):
    for dep in dependant.dependencies:
        yield dep.call
        yield from _calls(dep)


# Routes that limit MANAGER / EMPLOYEE to their branches INSIDE the handler or service (not visible in
# the dependencies). Keep in sync when such a route is added.
SCOPED_IN_SERVICE = {
    "/branches", "/inventory",
    "/users/{user_id}", "/users/{user_id}/branches", "/users/{user_id}/status", "/users/{user_id}/reset-password",
    "/customers/{customer_id}/orders", "/customers/{customer_id}/orders/{order_key}",
    "/notifications/{notification_id}/resend", "/preorders/{preorder_id}/notifications",
}


def access(path: str, route: APIRoute) -> str:
    calls = list(_calls(route.dependant))
    roles = [r for c in calls for r in getattr(c, "dkat_roles", ())]
    branch = any(getattr(c, "dkat_branch_scope", False) for c in calls)
    branch = branch or path.removeprefix(settings.API_V1_PREFIX) in SCOPED_IN_SERVICE
    if not roles and not branch and require_auth not in calls:
        return "Công khai" + (" (giới hạn 60 request/phút/IP)" if path.startswith(f"{settings.API_V1_PREFIX}/public") else "")
    who = " + ".join(r for r in ROLE_ORDER if r in set(roles)) if roles else "Mọi vai trò"
    return who + (", theo chi nhánh được phân công" if branch else "")


def first_line(text: str | None) -> str:
    return (text or "").strip().splitlines()[0].strip() if (text or "").strip() else ""


def build() -> tuple[str, str]:
    app = create_app()
    routes = sorted(iter_routes(app.routes), key=lambda pr: (pr[1].tags[0] if pr[1].tags else "", pr[0], sorted(pr[1].methods)[0]))
    groups: dict[str, list[str]] = {}
    for path, r in routes:
        tag = r.tags[0] if r.tags else "khác"
        for method in sorted(r.methods - {"HEAD"}):
            desc = first_line(r.description) or r.summary or r.name
            groups.setdefault(tag, []).append(f"| `{method}` | `{path}` | {access(path, r)} | {desc.replace('|', '/')} |")
    total = sum(len(v) for v in groups.values())
    md = [
        "# Danh sách API (sinh tự động)",
        "",
        f"Sinh bằng `python -m scripts.gen_api_docs` từ chính ứng dụng FastAPI: {total} endpoint. Không sửa tay file này.",
        "Quyền truy cập được đọc từ dependency của từng route (`require_auth`, `require_role`, `require_branch_access`).",
        "Đặc tả đầy đủ (tham số, schema request/response): `docs/openapi.json` (import được vào Postman / Swagger Editor),",
        "hoặc Swagger UI khi chạy backend: http://127.0.0.1:8000/docs",
        "",
        "Định dạng chung: thành công `{\"success\": true, \"data\": ...}`; lỗi `{\"success\": false, \"error\": {\"code\", \"message\", \"details\"}}`.",
        "Gửi token: header `Authorization: Bearer <token>` (lấy từ `POST /api/v1/auth/login`).",
        "",
    ]
    for tag in sorted(groups, key=lambda t: list(GROUP_TITLES).index(t) if t in GROUP_TITLES else 99):
        md += [f"## {GROUP_TITLES.get(tag, tag)}", "", "| Method | Đường dẫn | Quyền | Mô tả |", "|---|---|---|---|", *groups[tag], ""]
    spec = json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n"
    return "\n".join(md), spec


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    md, spec = build()
    targets = {DOCS / "api-endpoints.md": md, DOCS / "openapi.json": spec}
    if args.check:
        stale = [p.name for p, content in targets.items() if not p.exists() or p.read_text(encoding="utf-8") != content]
        print("Tài liệu API khớp với code" if not stale else f"Tài liệu API đã cũ: {stale} -> chạy python -m scripts.gen_api_docs")
        return 1 if stale else 0
    for p, content in targets.items():
        p.write_text(content, encoding="utf-8", newline="\n")
    print(f"Đã ghi {', '.join(p.name for p in targets)}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
