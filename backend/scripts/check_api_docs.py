"""Cross-check the documentation against the real API (docs/*.md, README.md, backend/README.md).

Run from backend/:  python -m scripts.check_api_docs        (exit code 1 on any mismatch)
1. docs/api-endpoints.md and docs/openapi.json are up to date (python -m scripts.gen_api_docs).
2. Every "METHOD /path" written in the documents exists in the app (with or without /api/v1;
   {anything} matches any path parameter; ?query is ignored).
3. Every function / setting named by docs/api-contract.md exists in the code.
"""
import importlib
import re
import sys
from pathlib import Path

from app.core.config import settings
from app.main import create_app
from scripts.gen_api_docs import build, iter_routes

ROOT = Path(__file__).resolve().parents[2]
DOCUMENTS = [*sorted((ROOT / "docs").glob("*.md")), ROOT / "README.md", ROOT / "backend" / "README.md"]
REF = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE)\s+`?(/[A-Za-z0-9_{}<>/\-.]+)")
CONTRACT_SYMBOLS = [
    ("app.modules.notifications.service", "NotificationService.notifyPreorder"),
    ("app.modules.notifications.service", "NotificationService.notifyPreorderAsync"),
    ("app.modules.notifications.service", "NotificationService.schedulePreorder"),
    ("app.modules.notifications.service", "NotificationService.EVENT_TYPES"),
    ("app.modules.notifications.templates", "render_template"),
    ("app.modules.notifications.templates", "TEMPLATE_READY_UNPAID"),
    ("app.modules.notifications.templates", "TEMPLATE_READY_PAID"),
    ("app.modules.notifications.retry", "resend_notification"),
    ("app.modules.notifications.retry", "retry_failed_notifications"),
    ("app.modules.customers.service", "upsert_customer_by_phone"),
    ("app.core.mailer", "send_email"),
    ("app.core.sms", "send_sms"),
    ("app.core.permissions", "get_accessible_branch_ids"),
    ("app.core.permissions", "ensure_branch_access"),
]
CONTRACT_SETTINGS = ["NOTIFY_SMS_CONFIRM_SECONDS", "NOTIFY_SMS_POLL_SECONDS", "NOTIFY_RETRY_INTERVAL_SECONDS",
                     "NOTIFY_MAX_RETRIES", "PREORDER_READY_DAYS", "STORE_CONTACT_PHONE"]


def normalize(path: str) -> str:
    path = path.split("?")[0].rstrip(".,;:)")
    path = path.removeprefix(settings.API_V1_PREFIX) or "/"
    path = re.sub(r"\{[^}]*\}|<[^>]*>", "{}", path)
    path = re.sub(r"/\d+(?=/|$)", "/{}", path)  # concrete ids in examples: /notifications/103/resend
    return path.rstrip("/") or "/"


def main() -> int:
    problems: list[str] = []
    md, spec = build()
    for name, content in (("api-endpoints.md", md), ("openapi.json", spec)):
        p = ROOT / "docs" / name
        if not p.exists() or p.read_text(encoding="utf-8") != content:
            problems.append(f"docs/{name} đã cũ -> chạy python -m scripts.gen_api_docs")

    real = {(m, normalize(path)) for path, r in iter_routes(create_app().routes) for m in r.methods}
    checked = 0
    for doc in DOCUMENTS:
        for n, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            for method, path in REF.findall(line):
                if not path.startswith(("/api/", "/auth", "/branches", "/users", "/customers", "/products", "/inventory",
                                        "/reports", "/notifications", "/preorders", "/public", "/health")):
                    continue
                checked += 1
                if (method, normalize(path)) not in real:
                    problems.append(f"{doc.relative_to(ROOT)}:{n}: {method} {path} không có trong API")

    for module, symbol in CONTRACT_SYMBOLS:
        obj = importlib.import_module(module)
        for part in symbol.split("."):
            obj = getattr(obj, part, None)
        if obj is None:
            problems.append(f"api-contract: {module}.{symbol} không tồn tại")
    problems += [f"api-contract: setting {s} không tồn tại" for s in CONTRACT_SETTINGS if not hasattr(settings, s)]

    print(f"Đã đối chiếu {checked} tham chiếu endpoint trong {len(DOCUMENTS)} tài liệu, {len(real)} endpoint thật, "
          f"{len(CONTRACT_SYMBOLS)} hàm và {len(CONTRACT_SETTINGS)} cấu hình trong hợp đồng.")
    for p in problems:
        print("  KHÔNG KHỚP:", p)
    print("=> Tài liệu khớp API thật" if not problems else f"=> {len(problems)} chỗ không khớp")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
