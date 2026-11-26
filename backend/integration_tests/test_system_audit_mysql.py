"""System audit flows on an isolated MySQL schema (scripts/test_system_audit_mysql.ps1).

Covers login, branch management, RBAC/branch scoping, stock import (CSV + XLSX,
validation, duplicate guard, movements), product creation with variants and
opening stock, and public pre-orders. Never run against team or production data.
"""
import io
import os
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import text

from app.core import config
from app.db.session import engine
from app.main import app

PASSWORD = "audit-test-password-123"


@unittest.skipUnless(os.getenv("DKAT_AUDIT_TEST_DB") == "1", "Requires isolated MySQL test database")
class SystemAuditMySQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database = engine.url.database or ""
        if engine.url.host not in {"127.0.0.1", "localhost"} or not database.startswith("dkat_") \
                or not database.endswith(("_test", "_e2e")):
            raise RuntimeError("Use a local, disposable dkat_*_test / dkat_*_e2e schema only")
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()
        cls.suffix = uuid4().hex[:8]
        owner = "own" + cls.suffix
        response = cls.client.post("/api/v1/admin/accounts", headers={"X-Admin-Token": config.ADMIN_TOKEN}, json={
            "shop_name": "Audit " + cls.suffix, "plan": "basic", "subscription_months": 12,
            "owner_username": owner, "owner_email": owner + "@example.test",
            "owner_full_name": "Owner", "owner_password": PASSWORD,
        })
        assert response.status_code == 201, response.text
        cls.owner = cls.login(owner)
        cls.b1 = cls.call("POST", "/api/v1/branches", cls.owner, {"name": "CN Một " + cls.suffix, "address": "HN"}, 201)
        cls.b2 = cls.call("POST", "/api/v1/branches", cls.owner, {"name": "CN Hai " + cls.suffix, "address": "HCM"}, 201)
        for role, branch in (("manager", cls.b1), ("staff", cls.b1)):
            cls.call("POST", "/api/v1/users", cls.owner, {
                "username": f"Audit{role.title()}{cls.suffix}", "full_name": role, "role": role,
                "password": PASSWORD, "branch_ids": [branch["id"]],
            }, 201)
        cls.manager = cls.login(f"audit{'manager'}{cls.suffix}")
        cls.staff = cls.login(f"AUDITSTAFF{cls.suffix}")
        category = cls.call("POST", "/api/v1/categories", cls.owner, {"name": "Áo " + cls.suffix}, 201)
        cls.category_id = category["categoryId"]

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)

    @classmethod
    def login(cls, username):
        response = cls.client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
        assert response.status_code == 200, (username, response.text)
        return {"Authorization": "Bearer " + response.json()["access_token"]}

    @classmethod
    def call(cls, method, path, headers=None, body=None, expected=200, **kwargs):
        response = cls.client.request(method, path, headers=headers, json=body, **kwargs)
        assert response.status_code == expected, (method, path, response.status_code, response.text)
        return response.json() if response.content else None

    def product(self, headers, sku, initial=0, branch=None):
        body = {
            "categoryId": self.category_id, "name": "Áo sơ mi " + sku,
            "variants": [{"variantName": "Trắng / M", "sku": sku, "price": 250000, "costPrice": 120000,
                          "initialQuantity": initial}],
        }
        if branch:
            body["stockBranchId"] = branch
        return self.call("POST", "/api/v1/products/full", headers, body, 201)

    # --- Authentication -------------------------------------------------
    def test_login_rules(self):
        login = lambda name, password=PASSWORD: self.client.post(
            "/api/v1/auth/login", json={"username": name, "password": password}).status_code
        self.assertEqual(login(f"auditmanager{self.suffix}"), 200)
        self.assertEqual(login(f"AuditManager{self.suffix}:manager"), 200)
        self.assertEqual(login(f"auditmanager{self.suffix}:staff"), 401)  # role suffix must match
        self.assertEqual(login(f"auditmanager{self.suffix}:boss"), 401)
        self.assertEqual(login(f"auditmanager{self.suffix}", "wrong-password-123"), 401)
        self.assertEqual(login("nobody" + self.suffix), 401)
        self.assertEqual(login(f"auditmanager{self.suffix}x"), 401)
        me = self.call("GET", "/api/v1/auth/me", self.manager)
        self.assertEqual((me["username"], me["role"]), (f"auditmanager{self.suffix}", "manager"))

    def test_locked_account_cannot_login_and_loses_session(self):
        user = self.call("POST", "/api/v1/users", self.owner, {
            "username": "lock" + self.suffix, "full_name": "Lock", "role": "staff", "password": PASSWORD,
        }, 201)
        headers = self.login("lock" + self.suffix)
        self.call("PATCH", f"/api/v1/users/{user['id']}/status", self.owner, {"status": "LOCKED"})
        self.assertEqual(self.client.get("/api/v1/auth/me", headers=headers).status_code, 401)
        self.assertEqual(self.client.post("/api/v1/auth/login", json={
            "username": "lock" + self.suffix, "password": PASSWORD}).status_code, 401)

    # --- Branches -------------------------------------------------------
    def test_branch_management(self):
        created = self.call("POST", "/api/v1/branches", self.owner,
                            {"name": "Chi nhánh mới " + self.suffix, "address": "Đà Nẵng", "phone": "0901234567"}, 201)
        self.assertRegex(created["branchCode"], r"^CN\d{2,}$")
        self.call("POST", "/api/v1/branches", self.owner,
                  {"name": "chi nhánh MỚI " + self.suffix, "address": "x"}, 409)  # duplicate name
        self.call("POST", "/api/v1/branches", self.owner,
                  {"branchCode": created["branchCode"].lower(), "name": "Khác " + self.suffix, "address": "x"}, 409)
        bad = self.client.post("/api/v1/branches", headers=self.owner, json={"branchCode": "cn 1", "name": "X", "address": "x"})
        self.assertEqual(bad.status_code, 422)
        self.assertIn("Mã chi nhánh", bad.json()["detail"][0]["msg"])
        updated = self.call("PUT", f"/api/v1/branches/{created['id']}", self.owner,
                            {"name": "Đã đổi " + self.suffix, "address": "Huế"})
        self.assertEqual((updated["branchCode"], updated["address"]), (created["branchCode"], "Huế"))
        self.call("POST", "/api/v1/branches", self.manager, {"name": "M", "address": "x"}, 403)
        self.call("PUT", f"/api/v1/branches/{self.b1['id']}", self.manager, {"name": "M", "address": "x"}, 403)
        self.call("GET", f"/api/v1/branches/{self.b2['id']}", self.manager, expected=403)
        visible = {branch["id"] for branch in self.call("GET", "/api/v1/branches", self.manager)}
        self.assertEqual(visible, {self.b1["id"]})

    # --- RBAC -----------------------------------------------------------
    def test_account_management_is_owner_only(self):
        for headers in (self.manager, self.staff):
            self.call("POST", "/api/v1/users", headers, {
                "username": "x" + uuid4().hex[:6], "full_name": "X", "role": "staff", "password": PASSWORD,
            }, 403)
        listing = self.call("GET", "/api/v1/users", self.manager)
        self.assertTrue(listing["items"])
        self.assertTrue(all(item["role"] == "employee" for item in listing["items"]))
        self.call("GET", f"/api/v1/users?branchId={self.b2['id']}", self.manager, expected=403)
        self.call("GET", "/api/v1/users", self.staff, expected=403)
        staff = [item for item in listing["items"] if item["username"] == f"auditstaff{self.suffix}"][0]
        self.call("PATCH", f"/api/v1/users/{staff['id']}/status", self.manager, {"status": "LOCKED"}, 403)
        self.call("PUT", f"/api/v1/users/{staff['id']}/branches", self.manager, {"branch_ids": []}, 403)
        owner_view = self.call("GET", "/api/v1/users?role=staff", self.owner)
        self.assertTrue(owner_view["items"])

    def test_catalog_and_stock_permissions(self):
        product = self.product(self.manager, "MGR-" + self.suffix)
        self.assertIsNone(product["variants"][0]["cost_price"])  # managers never see cost
        self.product(self.owner, "OWN-" + self.suffix)
        self.call("POST", "/api/v1/products/full", self.staff, {
            "categoryId": self.category_id, "name": "x", "variants": [{"variantName": "x", "price": 1}],
        }, 403)
        variant = product["variants"][0]["variant_id"]
        stock = {"branchId": self.b1["id"], "items": [{"variantId": variant, "quantity": 5}]}
        self.call("POST", "/api/v1/inventory/import", self.manager, stock, 201)
        self.call("POST", "/api/v1/inventory/import", self.staff, stock, 403)
        self.call("POST", "/api/v1/inventory/import", self.manager, {**stock, "branchId": self.b2["id"]}, 403)
        self.call("POST", "/api/v1/inventory/export", self.manager,
                  {**stock, "items": [{"variantId": variant, "quantity": 2}], "reason": "HU_HONG"}, 201)
        self.call("POST", "/api/v1/inventory/stocktake", self.manager,
                  {"branchId": self.b1["id"], "note": "Kiểm kê", "items": [{"variantId": variant, "countedQuantity": 10}]}, 201)
        rows = self.call("GET", f"/api/v1/inventory?branchId={self.b1['id']}&keyword=MGR-{self.suffix}", self.staff)
        self.assertEqual(rows[0]["quantity"], 10)
        self.call("GET", f"/api/v1/reports/summary?branchId={self.b1['id']}", self.manager)
        self.call("GET", f"/api/v1/reports/summary?branchId={self.b2['id']}", self.manager, expected=403)
        self.call("GET", f"/api/v1/reports/summary?branchId={self.b1['id']}", self.staff, expected=403)

    def test_product_full_creates_opening_stock_atomically(self):
        sku = "FULL-" + self.suffix
        product = self.product(self.owner, sku, initial=7, branch=self.b1["id"])
        rows = self.call("GET", f"/api/v1/inventory?branchId={self.b1['id']}&keyword={sku}", self.owner)
        self.assertEqual(rows[0]["quantity"], 7)
        moves = self.call("GET", f"/api/v1/inventory/movements?branchId={self.b1['id']}&variantId={product['variants'][0]['variant_id']}", self.owner)
        self.assertEqual([m["movementType"] for m in moves], ["IMPORT"])
        # A duplicate SKU rolls back the whole product, not just the variant.
        self.call("POST", "/api/v1/products/full", self.owner, {
            "categoryId": self.category_id, "name": "Rollback " + self.suffix,
            "variants": [{"variantName": "a", "sku": sku, "price": 1}],
        }, 409)
        self.assertEqual(self.call("GET", f"/api/v1/products?keyword=Rollback {self.suffix}", self.owner), [])
        self.call("POST", "/api/v1/products/full", self.manager, {
            "categoryId": self.category_id, "name": "Wrong branch",
            "variants": [{"variantName": "a", "price": 1, "initialQuantity": 1}], "stockBranchId": self.b2["id"],
        }, 403)

    # --- Stock import ---------------------------------------------------
    def upload(self, headers, name, content, *, dry_run=True, branch=None, allow_duplicate=False, expected=200):
        branch = branch or self.b1["id"]
        response = self.client.post(
            f"/api/v1/inventory/import-csv?branchId={branch}&dryRun={str(dry_run).lower()}"
            f"&allowDuplicate={str(allow_duplicate).lower()}",
            headers=headers, files={"file": (name, content, "application/octet-stream")},
        )
        self.assertEqual(response.status_code, expected, response.text)
        return response.json()

    def test_stock_import_csv_xlsx_validation_and_duplicates(self):
        sku = "IMP-" + self.suffix
        self.product(self.owner, sku)
        csv_body = f"SKU;Số lượng;Ghi chú;Tên sản phẩm\n{sku};4;Lô 1;Áo\n".encode("utf-8-sig")
        preview = self.upload(self.manager, "nhap.csv", csv_body)
        self.assertTrue(preview["valid"], preview)
        self.assertEqual((preview["rows"][0]["quantityBefore"], preview["rows"][0]["productName"]), (0, "Áo sơ mi " + sku))
        self.upload(self.manager, "nhap.csv", csv_body, dry_run=False, expected=201)
        duplicate = self.upload(self.manager, "nhap.csv", csv_body)
        self.assertIsNotNone(duplicate["duplicateOfImportAt"])
        blocked = self.upload(self.manager, "nhap.csv", csv_body, dry_run=False, expected=409)
        self.assertEqual(blocked["detail"]["code"], "DUPLICATE_STOCK_IMPORT")
        self.upload(self.manager, "nhap.csv", csv_body, dry_run=False, allow_duplicate=True, expected=201)

        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["sku", "quantity", "note"])
        sheet.append([sku, 3, "Excel"])
        sheet.append([sku, 2, None])              # duplicate row -> warning, summed
        sheet.append(["NOPE-" + self.suffix, 1, None])
        sheet.append([sku, -1, None])
        sheet.append([sku, 0, None])
        sheet.append([sku, "abc", None])
        buffer = io.BytesIO()
        workbook.save(buffer)
        result = self.upload(self.manager, "nhap.xlsx", buffer.getvalue())
        self.assertEqual(result["fileType"], "xlsx")
        self.assertFalse(result["valid"])
        self.assertEqual(sorted(e["code"] for e in result["errors"]), ["INVALID_VALUE"] * 3 + ["SKU_NOT_FOUND"])
        self.assertEqual([w["code"] for w in result["warnings"]], ["DUPLICATE_SKU_ROW"])
        self.upload(self.manager, "nhap.xlsx", buffer.getvalue(), dry_run=False, expected=422)
        rows = self.call("GET", f"/api/v1/inventory?branchId={self.b1['id']}&keyword={sku}", self.owner)
        self.assertEqual(rows[0]["quantity"], 8)  # invalid file wrote nothing

        bad_header = self.upload(self.manager, "x.csv", b"code,amount\nA,1\n")
        self.assertEqual(bad_header["errors"][0]["code"], "INVALID_HEADER")
        legacy = self.upload(self.manager, "x.xls", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"0" * 64)
        self.assertEqual(legacy["errors"][0]["code"], "UNSUPPORTED_XLS")
        self.upload(self.staff, "nhap.csv", csv_body, expected=403)
        self.upload(self.manager, "nhap.csv", csv_body, branch=self.b2["id"], expected=403)
        with engine.connect() as db:
            files = db.execute(text("""
                SELECT COUNT(*) FROM inventory_movements m JOIN inventory i ON i.inventory_id=m.inventory_id
                WHERE i.branch_id=:b AND m.reference_type='STOCK_FILE'
            """), {"b": self.b1["id"]}).scalar_one()
        self.assertEqual(files, 2)

    # --- Pre-orders -----------------------------------------------------
    def test_public_preorder_only_for_out_of_stock(self):
        sku = "PRE-" + self.suffix
        product = self.product(self.owner, sku)
        variant = product["variants"][0]["variant_id"]
        order = {"branchId": self.b1["id"], "customer": {"fullName": "Nguyễn Văn A", "phone": "0912345678",
                                                         "address": "1 Lê Lợi"},
                 "items": [{"variantId": variant, "quantity": 2}]}
        created = self.client.post("/api/v1/preorders", json=order)
        self.assertEqual(created.status_code, 201, created.text)
        self.assertTrue(created.json()["preorderCode"].startswith("PD-"))
        with engine.connect() as db:
            stored = db.execute(text("SELECT status, customer_address FROM preorders WHERE preorder_code=:c"),
                                {"c": created.json()["preorderCode"]}).one()
        self.assertEqual(tuple(stored), ("WAITING_STOCK", "1 Lê Lợi"))
        missing_address = self.client.post("/api/v1/preorders", json={**order, "customer": {"fullName": "A", "phone": "0912345678"}})
        self.assertEqual(missing_address.status_code, 422)
        self.call("POST", "/api/v1/inventory/import", self.owner,
                  {"branchId": self.b1["id"], "items": [{"variantId": variant, "quantity": 10}]}, 201)
        in_stock = self.client.post("/api/v1/preorders", json=order)
        self.assertEqual((in_stock.status_code, in_stock.json()["code"]), (409, "VARIANT_IN_STOCK"))


if __name__ == "__main__":
    unittest.main()
