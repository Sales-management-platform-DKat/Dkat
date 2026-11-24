"""Forbidden actions per role (FR-01.4, NFR-02) on the demo seed (python -m scripts.demo_reset). In-process.

    python -m scripts.check_forbidden

Every request uses a VALID body, so a 2xx means the action really went through (permission hole).
Expected: 403 (wrong role / branch) or 401 (no or wrong credentials). Accounts: owner01, manager01:manager
(CN01, CN02), staff01:staff (CN01). A second store is created through the admin API to test cross-store access.
"""
import sys
from uuid import uuid4

from app.core import config
from app.core.config import settings

PW = "DKat@Demo2026"
results: list[tuple[str, bool, str]] = []


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    settings.NOTIFY_RETRY_ENABLED = False
    settings.SMTP_HOST = settings.ESMS_API_KEY = ""  # nothing may be sent by this script
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        def login(u, pw=PW):
            r = c.post("/api/v1/auth/login", json={"username": u, "password": pw})
            return {"Authorization": "Bearer " + r.json()["access_token"]} if r.status_code == 200 else None

        owner, manager, staff = login("owner01"), login("manager01:manager"), login("staff01:staff")
        inv = c.get("/api/v1/inventory", headers=owner, params={"branchId": 1, "page": 1, "size": 100}).json()
        v = {r["sku"]: r["variantId"] for r in inv}
        product_id = inv[0]["productId"]
        category = c.get("/api/v1/categories", headers=owner).json()[0]["categoryId"]
        paid = next(o for o in c.get("/api/v1/sales-orders", headers=owner, params={"branchId": 1, "page": 1, "size": 20}).json()
                    if o["status"] == "PAID")["salesOrderId"]
        paid_cn02 = next(o for o in c.get("/api/v1/sales-orders", headers=owner, params={"branchId": 2, "page": 1, "size": 20}).json()
                         if o["status"] == "PAID")["salesOrderId"]
        staff_id = next(u["id"] for u in c.get("/api/v1/users", headers=owner).json()["items"] if u["username"] == "staff01")
        sale = {"branchId": 1, "items": [{"variantId": v["AT-COT-S"], "quantity": 1}]}
        stock = {"branchId": 1, "note": "thử quyền", "items": [{"variantId": v["AT-COT-S"], "quantity": 1}]}

        # second store (cross-store isolation)
        name = f"other{uuid4().hex[:6]}"
        c.post("/api/v1/admin/accounts", headers={"X-Admin-Token": config.ADMIN_TOKEN}, json={
            "shop_name": "Cửa hàng khác", "plan": "basic", "subscription_months": 12, "owner_username": name,
            "owner_full_name": name, "owner_password": "other-store-password", "owner_email": f"{name}@example.com"})
        other = login(name, "other-store-password")

        cases = [
            # (role, action, method, path, body/params, auth)
            ("EMPLOYEE", "Tạo sản phẩm", "POST", "/api/v1/products", {"categoryId": category, "name": "Không được tạo"}, staff),
            ("EMPLOYEE", "Tạo danh mục", "POST", "/api/v1/categories", {"name": "Không được tạo"}, staff),
            ("EMPLOYEE", "Sửa giá biến thể", "PUT", f"/api/v1/variants/{v['AT-COT-S']}", {"variantName": "X", "price": "1"}, staff),
            ("EMPLOYEE", "Nhập kho", "POST", "/api/v1/inventory/import", stock, staff),
            ("EMPLOYEE", "Xuất kho", "POST", "/api/v1/inventory/export", {**stock, "reason": "KHAC"}, staff),
            ("EMPLOYEE", "Kiểm kê", "POST", "/api/v1/inventory/stocktake",
             {"branchId": 1, "note": "thử", "items": [{"variantId": v["AT-COT-S"], "countedQuantity": 99}]}, staff),
            ("EMPLOYEE", "Hoàn đơn đã thanh toán", "POST", f"/api/v1/sales-orders/{paid}/refund", {"reason": "thử"}, staff),
            ("EMPLOYEE", "Xem báo cáo doanh thu", "GET", "/api/v1/reports/revenue", {"branchId": 1}, staff),
            ("EMPLOYEE", "Xuất CSV doanh thu", "GET", "/api/v1/reports/revenue/export", {"branchId": 1}, staff),
            ("EMPLOYEE", "Xem danh sách nhân viên", "GET", "/api/v1/users", None, staff),
            ("EMPLOYEE", "Tạo tài khoản", "POST", "/api/v1/users", {"username": "x" + uuid4().hex[:6], "full_name": "X", "password": "Abcdef@123456", "role": "staff", "branch_ids": [1]}, staff),
            ("EMPLOYEE", "Tạo chi nhánh", "POST", "/api/v1/branches", {"branchCode": "X1", "name": "X", "address": "X"}, staff),
            ("EMPLOYEE", "Bán ở chi nhánh khác (CN02)", "POST", "/api/v1/sales-orders", {**sale, "branchId": 2}, staff),
            ("EMPLOYEE", "Xem tồn kho CN02", "GET", "/api/v1/inventory", {"branchId": 2}, staff),
            ("EMPLOYEE", "Xem đặt trước CN02", "GET", "/api/v1/preorders", {"branchId": 2}, staff),
            ("MANAGER", "Tạo chi nhánh", "POST", "/api/v1/branches", {"branchCode": "X2", "name": "X", "address": "X"}, manager),
            ("MANAGER", "Ngừng hoạt động chi nhánh", "PATCH", "/api/v1/branches/2/status", {"status": "INACTIVE"}, manager),
            ("MANAGER", "Tạo sản phẩm", "POST", "/api/v1/products", {"categoryId": category, "name": "Không được tạo"}, manager),
            ("MANAGER", "Ngừng bán sản phẩm", "PATCH", f"/api/v1/products/{product_id}/status", {"status": "INACTIVE"}, manager),
            ("MANAGER", "Xem / quản lý nhân viên", "GET", "/api/v1/users", None, manager),
            ("MANAGER", "Khóa tài khoản nhân viên", "PATCH", f"/api/v1/users/{staff_id}/status", {"status": "LOCKED"}, manager),
            ("MANAGER", "Báo cáo CN03 (không phân công)", "GET", "/api/v1/reports/summary", {"branchId": 3}, manager),
            ("MANAGER", "Nhập kho CN03", "POST", "/api/v1/inventory/import", {**stock, "branchId": 3}, manager),
            ("MANAGER", "Bán ở CN03", "POST", "/api/v1/sales-orders", {**sale, "branchId": 3}, manager),
            ("OWNER cửa hàng khác", "Xem đơn bán của DKat Fashion", "GET", f"/api/v1/sales-orders/{paid}", None, other),
            ("OWNER cửa hàng khác", "Hoàn đơn của DKat Fashion", "POST", f"/api/v1/sales-orders/{paid_cn02}/refund", {"reason": "thử"}, other),
            ("OWNER cửa hàng khác", "Xem tồn kho chi nhánh DKat", "GET", "/api/v1/inventory", {"branchId": 1}, other),
            ("OWNER cửa hàng khác", "Nhập kho chi nhánh DKat", "POST", "/api/v1/inventory/import", stock, other),
            ("Không đăng nhập", "Tạo đơn POS", "POST", "/api/v1/sales-orders", sale, None),
            ("Không đăng nhập", "Xem báo cáo", "GET", "/api/v1/reports/summary", None, None),
            ("OWNER", "Tạo cửa hàng qua API quản trị khi không có X-Admin-Token", "POST", "/api/v1/admin/accounts",
             {"shop_name": "X", "plan": "basic", "subscription_months": 1, "owner_username": "y" + uuid4().hex[:6], "owner_full_name": "Y",
              "owner_password": "Abcdef@123456", "owner_email": "y@example.com"}, owner),
        ]
        for role, action, method, path, payload, auth in cases:
            kwargs = {"params": payload} if method == "GET" else {"json": payload}
            r = c.request(method, path, headers=auth or {}, **kwargs)
            ok = r.status_code in (401, 403, 404) if role.startswith("OWNER cửa hàng khác") else r.status_code in (401, 403)
            results.append((f"{role}: {action}", ok, f"{method} {path} -> {r.status_code} {r.text[:90]}"))
            print(f"{'PASS' if ok else 'FAIL'}  {role}: {action}  -> {r.status_code} {'' if ok else r.text[:160]}", flush=True)

    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} thao tác bị chặn đúng")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
