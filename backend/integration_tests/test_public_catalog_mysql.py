"""FR-07 public catalog (/api/v1/public/*) against a disposable local MySQL (dkat_catalog_test).

    DKAT_CATALOG_TEST_DB=1 DB_NAME=dkat_catalog_test python -m unittest -v integration_tests.test_public_catalog_mysql

Fixture (store A, everything created through the staff API):
  categories  Thời trang > Áo > Áo khoác ; Thời trang > Quần ; Ngừng bán (INACTIVE) > Cũ
  Áo khoác gió   Đen/M 300k (no stock), Đen/L 320k (3 at branch A1), Trắng/M 999k INACTIVE   [Áo khoác]
  Áo thun        Trắng/S 150k (no stock, 1 pre-ordered -> held)                                [Áo]
  Quần jean      Xanh/30 400k (5 at branch A2)                                                 [Quần]
  Hàng cũ        Đen/M 50k (in stock) but its category sub-tree is INACTIVE                     [Cũ]
  Ẩn             INACTIVE product
Store B has its own product; with two stores storeId is required.
"""
import json
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
from app.modules.catalog.router import public_limiter

INTERNAL = ("cost", "quantity", "reserved", "allocated", "productcode", "product_code", "storeid", "store_id",
            "status", "createdat", "created_at", "barcode")


@unittest.skipUnless(os.getenv("DKAT_CATALOG_TEST_DB") == "1", "Requires isolated MySQL test database")
class PublicCatalogMySQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if engine.url.host not in {"127.0.0.1", "localhost"} or engine.url.database != "dkat_catalog_test":
            raise RuntimeError("Use a local, disposable dkat_catalog_test schema only")
        settings.NOTIFY_RETRY_ENABLED = False
        settings.SMTP_HOST = settings.ESMS_API_KEY = ""  # nothing is sent
        with engine.begin() as db:
            db.execute(text("DELETE FROM preorder_request_limits"))
        cls.client = TestClient(app)
        cls.client.__enter__()
        public_limiter.reset()
        cls.a = cls.provision_store_a()
        cls.b = cls.provision_store_b()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)

    @classmethod
    def owner(cls, prefix):
        name = f"{prefix}{uuid4().hex[:8]}"
        r = cls.client.post("/api/v1/admin/accounts", headers={"X-Admin-Token": config.ADMIN_TOKEN}, json={
            "shop_name": name, "plan": "basic", "subscription_months": 12, "owner_username": name,
            "owner_full_name": name, "owner_password": "catalog-test-password", "owner_email": f"{name}@example.com"})
        assert r.status_code == 201, r.text
        token = cls.client.post("/api/v1/auth/login", json={"username": name, "password": "catalog-test-password"}).json()["access_token"]
        return r.json()["shop_id"], {"Authorization": f"Bearer {token}"}

    @classmethod
    def call(cls, auth, method, path, body, expect=(200, 201)):
        r = cls.client.request(method, f"/api/v1{path}", headers=auth, json=body)
        assert r.status_code in expect, (path, r.status_code, r.text)
        return r.json()

    @classmethod
    def provision_store_a(cls):
        store, auth = cls.owner("cata")
        c = lambda name, parent=None: cls.call(auth, "POST", "/categories", {"name": name, "parentCategoryId": parent})["categoryId"]  # noqa: E731
        fashion = c("Thời trang")
        shirts = c("Áo", fashion)
        jackets = c("Áo khoác", shirts)
        pants = c("Quần", fashion)
        retired = c("Ngừng bán")
        old = c("Cũ", retired)
        branches = [cls.call(auth, "POST", "/branches", {"branchCode": code, "name": f"Chi nhánh {code}", "address": f"{code} Lê Lợi"})["id"]
                    for code in ("A1", "A2")]
        attr = {n: cls.call(auth, "POST", "/attributes", {"name": n, "dataType": "TEXT"})["attributeId"] for n in ("Màu", "Size")}

        def product(name, category, variants):
            pid = cls.call(auth, "POST", "/products", {"categoryId": category, "name": name, "description": f"Mô tả {name}"})["productId"]
            ids = []
            for color, size, price in variants:
                ids.append(cls.call(auth, "POST", f"/products/{pid}/variants", {
                    "sku": f"{store}-{uuid4().hex[:8]}", "variantName": f"{color} / {size}", "price": str(price), "costPrice": "12345",
                    "attributes": [{"attributeId": attr["Màu"], "value": color}, {"attributeId": attr["Size"], "value": size}]})["variant_id"])
            return pid, ids

        jacket, jv = product("Áo khoác gió", jackets, [("Đen", "M", 300000), ("Đen", "L", 320000), ("Trắng", "M", 999000)])
        tee, tv = product("Áo thun", shirts, [("Trắng", "S", 150000)])
        jean, nv = product("Quần jean", pants, [("Xanh", "30", 400000)])
        relic, rv = product("Hàng cũ", old, [("Đen", "M", 50000)])
        hidden, _ = product("Ẩn", shirts, [("Đen", "M", 1)])
        cls.call(auth, "PATCH", f"/variants/{jv[2]}/status", {"status": "INACTIVE"})
        cls.call(auth, "PATCH", f"/products/{hidden}/status", {"status": "INACTIVE"})
        imp = lambda b, v, q: cls.call(auth, "POST", "/inventory/import", {"branchId": b, "items": [{"variantId": v, "quantity": q}]})  # noqa: E731
        imp(branches[0], jv[1], 3)
        imp(branches[1], nv[0], 5)
        imp(branches[0], rv[0], 2)
        cls.call(auth, "PATCH", f"/categories/{retired}/status", {"status": "INACTIVE"})
        # Áo thun: pre-ordered while empty, then 1 imported -> the unit is held, never available
        r = cls.client.post("/api/v1/preorders", json={"branchId": branches[0], "items": [{"variantId": tv[0], "quantity": 1}],
                                                       "customer": {"fullName": "Khách", "phone": "0911111111", "address": "1"}})
        assert r.status_code == 201, r.text
        imp(branches[0], tv[0], 1)
        return {"store": store, "auth": auth, "branches": branches, "cats": {"fashion": fashion, "shirts": shirts, "jackets": jackets,
                "pants": pants, "retired": retired, "old": old}, "jacket": jacket, "jv": jv, "tee": tee, "jean": jean, "relic": relic, "hidden": hidden}

    @classmethod
    def provision_store_b(cls):
        store, auth = cls.owner("catb")
        cat = cls.call(auth, "POST", "/categories", {"name": "Áo"})["categoryId"]
        pid = cls.call(auth, "POST", "/products", {"categoryId": cat, "name": "Áo của cửa hàng B"})["productId"]
        cls.call(auth, "POST", f"/products/{pid}/variants", {"sku": f"B-{uuid4().hex[:8]}", "variantName": "M", "price": "1000"})
        return {"store": store, "product": pid}

    def get(self, path, store=None, **params):
        public_limiter.reset()
        return self.client.get(f"/api/v1/public{path}", params={"storeId": store or self.a["store"], **params})

    def names(self, **params):
        r = self.get("/products", **params)
        self.assertEqual(r.status_code, 200, r.text)
        return [i["name"] for i in r.json()["items"]]

    def test_no_login_and_allowlist_only(self):
        responses = [self.get("/products"), self.get(f"/products/{self.a['jacket']}"), self.get("/categories"), self.get("/branches")]
        self.assertEqual([r.status_code for r in responses], [200] * 4)
        raw = json.dumps([r.json() for r in responses], ensure_ascii=False)
        for word in INTERNAL:
            self.assertNotIn(f'"{word}', raw.lower().replace("_", "_"), word)
        self.assertNotIn("12345", raw)  # cost price
        card = responses[0].json()["items"][0]
        self.assertEqual(set(card), {"id", "name", "imageUrl", "category", "priceMin", "priceMax", "inStock"})

    def test_only_active_products_and_variants_with_price_range(self):
        page = self.get("/products").json()
        by_name = {i["name"]: i for i in page["items"]}
        self.assertEqual(sorted(by_name), ["Quần jean", "Áo khoác gió", "Áo thun"])  # Ẩn INACTIVE, Hàng cũ in an INACTIVE sub-tree
        jacket = by_name["Áo khoác gió"]
        self.assertEqual((jacket["priceMin"], jacket["priceMax"]), (300000.0, 320000.0))  # 999k variant is INACTIVE
        self.assertEqual(jacket["category"], {"id": self.a["cats"]["jackets"], "name": "Áo khoác"})
        self.assertEqual({n: i["inStock"] for n, i in by_name.items()}, {"Áo khoác gió": True, "Áo thun": False, "Quần jean": True})

    def test_category_tree_and_category_filter_with_descendants(self):
        tree = self.get("/categories").json()
        # Vietnamese collation order: "Áo" (A) before "Quần"; INACTIVE "Ngừng bán" and its child "Cũ" are absent
        self.assertEqual(tree, [{"id": self.a["cats"]["fashion"], "name": "Thời trang", "children": [
            {"id": self.a["cats"]["shirts"], "name": "Áo", "children": [{"id": self.a["cats"]["jackets"], "name": "Áo khoác", "children": []}]},
            {"id": self.a["cats"]["pants"], "name": "Quần", "children": []},
        ]}])
        self.assertEqual(sorted(self.names(categoryId=self.a["cats"]["shirts"])), ["Áo khoác gió", "Áo thun"])
        self.assertEqual(self.names(categoryId=self.a["cats"]["jackets"]), ["Áo khoác gió"])
        self.assertEqual(self.names(categoryId=self.a["cats"]["old"]), [])  # hidden sub-tree: empty, no error
        self.assertEqual(self.names(categoryId=999999999), [])

    def test_keyword_attr_and_in_stock_filters(self):
        self.assertEqual(self.names(keyword="khoác"), ["Áo khoác gió"])
        self.assertEqual(self.names(keyword="%"), [])  # LIKE wildcards are escaped
        self.assertEqual(sorted(self.names(attr="Màu:Đen")), ["Áo khoác gió"])  # Hàng cũ is hidden
        self.assertEqual(self.names(attr=["Màu:Trắng", "Size:M"]), [])  # Trắng/M exists only as an INACTIVE variant
        self.assertEqual(self.names(attr=["màu:trắng", "size:s"]), ["Áo thun"])  # case-insensitive, same variant
        self.assertEqual(sorted(self.names(inStock="true")), ["Quần jean", "Áo khoác gió"])
        self.assertEqual(self.names(inStock="false"), ["Áo thun"])  # its only unit is held for a pre-order
        self.assertEqual(self.get("/products", attr="sai").status_code, 422)
        self.assertEqual(self.get("/products", attr=[f"a:{i}" for i in range(6)]).status_code, 422)

    def test_paging(self):
        first = self.get("/products", size=2, page=1).json()
        second = self.get("/products", size=2, page=2).json()
        self.assertEqual((first["total"], first["totalPages"], len(first["items"]), len(second["items"])), (3, 2, 2, 1))
        self.assertEqual(self.get("/products", size=51).status_code, 422)
        self.assertEqual(self.get("/products", page=0).status_code, 422)

    def test_detail_per_branch_availability_and_hidden_products(self):
        d = self.get(f"/products/{self.a['jacket']}").json()
        a1, a2 = self.a["branches"]
        self.assertEqual([(v["name"], {b["branchId"]: b["availability"] for b in v["branches"]}) for v in d["variants"]],
                         [("Đen / M", {a1: "OUT_OF_STOCK", a2: "OUT_OF_STOCK"}), ("Đen / L", {a1: "IN_STOCK", a2: "OUT_OF_STOCK"})])
        self.assertEqual(d["variants"][0]["attributes"], [{"name": "Màu", "value": "Đen"}, {"name": "Size", "value": "M"}])
        for pid in (self.a["hidden"], self.a["relic"], 999999999):
            self.assertEqual(self.client.get(f"/api/v1/public/products/{pid}").status_code, 404, pid)

    def test_store_isolation_and_store_id_required_with_several_stores(self):
        self.assertNotIn("Áo của cửa hàng B", self.names())
        self.assertEqual(self.names(store=self.b["store"]), ["Áo của cửa hàng B"])
        public_limiter.reset()
        r = self.client.get("/api/v1/public/products")
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"]["details"][0]["field"], "storeId")

    def test_rate_limit_per_ip(self):
        public_limiter.reset()
        with patch.object(public_limiter, "limit", 3):
            rs = [self.client.get("/api/v1/public/categories", params={"storeId": self.a["store"]}) for _ in range(4)]
        public_limiter.reset()
        self.assertEqual([r.status_code for r in rs], [200, 200, 200, 429])
        self.assertEqual(rs[0].headers["x-ratelimit-remaining"], "2")
        self.assertTrue(int(rs[3].headers["retry-after"]) >= 1)
        self.assertEqual(rs[3].json()["detail"]["code"], "RATE_LIMIT_EXCEEDED")


if __name__ == "__main__":
    unittest.main()
