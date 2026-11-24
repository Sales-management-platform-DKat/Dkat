"""FR-07 public catalog (/api/v1/public/*) against a disposable local MySQL (dkat_catalog_test).

    DKAT_CATALOG_TEST_DB=1 DB_NAME=dkat_catalog_test python -m unittest -v integration_tests.test_public_catalog_mysql
"""
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core import config
from app.core.config import settings
from app.db.session import engine
from app.main import app
from app.modules.catalog import router as catalog

ALLOWED_PRODUCT = {"productId", "name", "description", "imageUrl", "categoryName", "variants"}
ALLOWED_VARIANT = {"variantId", "sku", "variantName", "price", "stock"}


@unittest.skipUnless(os.getenv("DKAT_CATALOG_TEST_DB") == "1", "Requires isolated MySQL test database")
class PublicCatalogMySQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if engine.url.host not in {"127.0.0.1", "localhost"} or engine.url.database != "dkat_catalog_test":
            raise RuntimeError("Use a local, disposable dkat_catalog_test schema only")
        settings.NOTIFY_RETRY_ENABLED = False
        settings.SMTP_HOST = settings.ESMS_API_KEY = ""  # notifications are recorded as NOT_CONFIGURED
        with engine.begin() as db:
            db.execute(text("DELETE FROM preorder_request_limits"))
        cls.client = TestClient(app)
        cls.client.__enter__()
        cls.store, cls.owner, cls.branches, cls.v = cls.provision()
        cls.other_store, *_ = cls.provision()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)

    @classmethod
    def provision(cls):
        name = f"cat{uuid4().hex[:8]}"
        r = cls.client.post("/api/v1/admin/accounts", headers={"X-Admin-Token": config.ADMIN_TOKEN}, json={
            "shop_name": name, "plan": "basic", "subscription_months": 12, "owner_username": name,
            "owner_full_name": name, "owner_password": "catalog-test-password", "owner_email": f"{name}@example.com"})
        assert r.status_code == 201, r.text
        store = r.json()["shop_id"]
        token = cls.client.post("/api/v1/auth/login", json={"username": name, "password": "catalog-test-password"}).json()["access_token"]
        auth = {"Authorization": f"Bearer {token}"}
        branches = [cls.client.post("/api/v1/branches", headers=auth, json={
            "branchCode": code, "name": f"Chi nhánh {code}", "address": f"{code} Lê Lợi", "phone": None}).json()["id"]
            for code in ("A", "B")]
        category = cls.client.post("/api/v1/categories", headers=auth, json={"name": "Áo"}).json()["categoryId"]
        product = cls.client.post("/api/v1/products", headers=auth, json={"categoryId": category, "name": f"Áo {name}"}).json()["productId"]
        v = [cls.client.post(f"/api/v1/products/{product}/variants", headers=auth, json={
            "sku": f"{name}-{i}", "variantName": f"Size {i}", "price": "150000", "costPrice": "90000"}).json()["variant_id"]
             for i in range(3)]
        cls.client.patch(f"/api/v1/variants/{v[2]}/status", headers=auth, json={"status": "INACTIVE"})
        hidden = cls.client.post("/api/v1/products", headers=auth, json={"categoryId": category, "name": f"Ẩn {name}"}).json()["productId"]
        cls.client.post(f"/api/v1/products/{hidden}/variants", headers=auth, json={"sku": f"{name}-h", "variantName": "H", "price": "1"})
        cls.client.patch(f"/api/v1/products/{hidden}/status", headers=auth, json={"status": "INACTIVE"})
        r = cls.client.post("/api/v1/inventory/import", headers=auth, json={"branchId": branches[0], "items": [{"variantId": v[0], "quantity": 3}]})
        assert r.status_code == 201, r.text
        return store, auth, branches, v

    def products(self, store=None, **params):
        r = self.client.get("/api/v1/public/products", params={"storeId": store or self.store, **params})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def stock_of(self, variant_id):
        for p in self.products():
            for v in p["variants"]:
                if v["variantId"] == variant_id:
                    return {s["branchId"]: s["status"] for s in v["stock"]}
        return None

    def test_allowlist_only_and_no_internal_fields(self):
        body = self.products()
        self.assertEqual(len(body), 1)  # INACTIVE product hidden
        self.assertEqual(set(body[0]), ALLOWED_PRODUCT)
        for variant in body[0]["variants"]:
            self.assertEqual(set(variant), ALLOWED_VARIANT)
        raw = self.client.get("/api/v1/public/products", params={"storeId": self.store}).text
        for leaked in ("costPrice", "cost_price", "90000", "quantity", "storeId", "productCode"):
            self.assertNotIn(leaked, raw)

    def test_stock_status_per_branch_and_inactive_variant_hidden(self):
        a, b = self.branches
        self.assertEqual(self.stock_of(self.v[0]), {a: "IN_STOCK", b: "OUT_OF_STOCK"})
        self.assertEqual(self.stock_of(self.v[1]), {a: "OUT_OF_STOCK", b: "OUT_OF_STOCK"})
        self.assertIsNone(self.stock_of(self.v[2]))  # INACTIVE variant

    def test_stock_held_for_preorders_is_not_available(self):
        a, _ = self.branches
        r = self.client.post("/api/v1/preorders", json={"branchId": a, "items": [{"variantId": self.v[1], "quantity": 1}],
                                                        "customer": {"fullName": "Khách", "phone": "0911111111", "address": "1"}})
        self.assertEqual(r.status_code, 201, r.text)
        imp = self.client.post("/api/v1/inventory/import", headers=self.owner, json={"branchId": a, "items": [{"variantId": self.v[1], "quantity": 1}]})
        self.assertEqual(imp.status_code, 201, imp.text)
        self.assertEqual(self.stock_of(self.v[1])[a], "OUT_OF_STOCK")  # the unit is held for the pre-order

    def test_branches_keyword_and_store_isolation(self):
        branches = self.client.get("/api/v1/public/branches", params={"storeId": self.store}).json()
        self.assertEqual([b["branchId"] for b in branches], self.branches)
        self.assertEqual(set(branches[0]), {"branchId", "name", "address", "phone"})
        self.assertEqual(self.products(keyword="khong-co-san-pham-nay"), [])
        other = self.products(store=self.other_store)
        self.assertTrue(all(v["variantId"] not in self.v for p in other for v in p["variants"]))
        self.assertEqual(self.client.get("/api/v1/public/products").status_code, 422)  # storeId required

    def test_rate_limit_per_ip(self):
        with patch.object(catalog, "RATE_LIMIT_PER_MINUTE", 3):
            catalog._hits.clear()
            codes = [self.client.get("/api/v1/public/branches", params={"storeId": self.store}).status_code for _ in range(4)]
        catalog._hits.clear()
        self.assertEqual(codes, [200, 200, 200, 429])


if __name__ == "__main__":
    unittest.main()
