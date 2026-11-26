"""OWNER CSV import: validation, preview, atomic writes and concurrency on isolated MySQL."""
import csv
import io
import itertools
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core import config
from app.db.session import engine
from app.main import app
from app.modules.products.csv_parser import COLUMNS, MAX_FILE_BYTES
from app.modules.products import csv_service


@unittest.skipUnless(os.getenv("DKAT_CSV_TEST_DB") == "1", "Requires isolated MySQL test database")
class ProductCsvMySQLTests(unittest.TestCase):
    seq = itertools.count(1)

    @classmethod
    def setUpClass(cls):
        if engine.url.host not in {"127.0.0.1", "localhost"} or engine.url.database != "dkat_pbi111_test":
            raise RuntimeError("Use a local, disposable dkat_pbi111_test schema only")
        cls.suffix = uuid4().hex[:10]
        cls.password = "pbi111-test-password-123"
        cls.store, cls.owner, cls.uid = cls.provision("owner")
        cls.other_store, cls.other_owner, _ = cls.provision("other")
        cls.roles = []
        for role in ("manager", "staff"):
            name = role + cls.suffix
            with TestClient(app, base_url="http://testserver/api/v1") as client:
                r = client.post("/users", headers=cls.owner, json={"username": name, "full_name": role,
                                "role": role, "password": cls.password})
                assert r.status_code == 201, r.text
                r = client.post("/auth/login", json={"username": name + ":" + role, "password": cls.password})
                assert r.status_code == 200, r.text
                cls.roles.append({"Authorization": "Bearer " + r.json()["access_token"]})
        with engine.begin() as db:
            cls.branches = [db.execute(text("""
                INSERT INTO branches (store_id,branch_code,name,address,status) VALUES (:s,:n,:n,'QA',:status)
            """), {"s": cls.store, "n": str(i), "status": "INACTIVE" if i == 2 else "ACTIVE"}).lastrowid
                for i in range(3)]

    @classmethod
    def provision(cls, prefix):
        name = prefix + cls.suffix
        with TestClient(app, base_url="http://testserver/api/v1") as client:
            r = client.post("/admin/accounts", headers={"X-Admin-Token": config.ADMIN_TOKEN}, json={
                "shop_name": name, "plan": "basic", "subscription_months": 12, "owner_username": name, "owner_email": name + "@example.test",
                "owner_full_name": name, "owner_password": cls.password,
            })
            assert r.status_code == 201, r.text
            store = r.json()["shop_id"]
            r = client.post("/auth/login", json={"username": name, "password": cls.password})
            assert r.status_code == 200, r.text
            return store, {"Authorization": "Bearer " + r.json()["access_token"]}, r.json()["user"]["id"]

    def setUp(self):
        token = f"{self.suffix}-{next(self.seq)}"
        self.row = {"product_name": "Sản phẩm " + token, "category": "Danh mục " + token,
                    "variant_name": "Đỏ", "sku": "SKU-" + token, "price": "12.50", "cost_price": "5.25",
                    "attributes": "Màu " + token + ":Đỏ"}

    def csv_bytes(self, rows, header=COLUMNS):
        content = io.StringIO(newline="")
        writer = csv.DictWriter(content, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)
        return content.getvalue().encode("utf-8")

    def submit(self, rows=None, *, content=None, dry=True, status=200, auth=None):
        content = self.csv_bytes([self.row] if rows is None else rows) if content is None else content
        with TestClient(app, base_url="http://testserver/api/v1") as client:
            response = client.post("/products/import-csv", params={"dryRun": str(dry).lower()},
                                   headers=self.owner if auth is None else auth,
                                   files={"file": ("products.csv", content, "text/csv")})
        self.assertEqual(response.status_code, status, response.text)
        return response.json()

    def snapshot(self):
        with engine.connect() as db:
            return tuple(db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one() for table in (
                "categories", "products", "attributes", "product_variants", "variant_attribute_values", "inventory", "inventory_movements"))

    def test_sample_20_rows_preview_then_import_uses_shared_services(self):
        sample = (Path(__file__).resolve().parents[2] / "data/sample-products.csv").read_bytes()
        before = self.snapshot()
        preview = self.submit(content=sample)
        self.assertTrue(preview["valid"])
        self.assertEqual(preview["summary"], {"categories": 2, "products": 5, "variants": 20, "attributes": 3})
        self.assertEqual(self.snapshot(), before)
        with patch.object(csv_service.service, "create_product", wraps=csv_service.service.create_product) as product_fn, \
             patch.object(csv_service.variant_service, "save_variant", wraps=csv_service.variant_service.save_variant) as variant_fn:
            result = self.submit(content=sample, dry=False, status=201)
        self.assertEqual((product_fn.call_count, variant_fn.call_count), (5, 20))
        self.assertEqual(len(result["rows"]), 20)
        self.assertEqual(self.snapshot(), tuple(a+b for a,b in zip(before, (2, 5, 3, 20, 38, 40, 0))))
        with engine.connect() as db:
            created = db.execute(text("""
                SELECT DISTINCT p.created_by,i.branch_id,i.quantity FROM inventory i
                JOIN product_variants v ON v.variant_id=i.variant_id JOIN products p ON p.product_id=v.product_id
                WHERE v.sku LIKE 'CSV111-%'
            """)).all()
        self.assertEqual(set(created), {(self.uid, self.branches[0], 0), (self.uid, self.branches[1], 0)})
        before = self.snapshot()
        repeated = self.submit(content=sample, dry=False, status=422)
        self.assertEqual(len(repeated["detail"]["errors"]), 20)
        self.assertEqual(self.snapshot(), before)

    def test_one_bad_row_rejects_entire_file_with_line_numbers(self):
        rows = [{**self.row, "sku": self.row["sku"] + "-ROW-" + str(i)} for i in range(20)]
        rows[8]["price"] = "-1"
        before = self.snapshot()
        preview = self.submit(rows)
        self.assertFalse(preview["valid"])
        self.assertEqual(preview["validRows"], 19)
        self.assertEqual(preview["errors"][0]["line"], 10)
        result = self.submit(rows, dry=False, status=422)
        self.assertEqual(result["detail"]["errors"][0]["field"], "price")
        self.assertEqual(self.snapshot(), before)

    def test_authentication_owner_only_and_store_isolation(self):
        before = self.snapshot()
        self.submit(auth={}, status=401)
        manager, staff = self.roles
        # Catalog maintenance is owner + manager (docs/rbac-matrix.md); a dry run writes nothing.
        self.submit(auth=manager, status=200)
        self.submit(auth=staff, status=403)
        with TestClient(app, base_url="http://testserver/api/v1") as client:
            r = client.post("/products/import-csv", headers=self.owner)
        self.assertEqual(r.status_code, 422)
        self.assertEqual(self.snapshot(), before)
        other = self.submit(auth=self.other_owner, dry=False, status=201)
        with engine.connect() as db:
            store = db.execute(text("SELECT store_id FROM products WHERE product_id=:id"),
                               {"id": other["rows"][0]["productId"]}).scalar_one()
        self.assertEqual(store, self.other_store)
        # Global SKU conflict is reported without exposing another store.
        self.assertEqual(self.submit()["errors"][0]["code"], "DUPLICATE_SKU")

    def test_existing_category_product_and_typed_attributes_are_reused(self):
        with TestClient(app, base_url="http://testserver/api/v1") as client:
            cat = client.post("/categories", headers=self.owner, json={"name": self.row["category"]}).json()["categoryId"]
            product = client.post("/products", headers=self.owner, json={"name": self.row["product_name"], "categoryId": cat,
                                  "productCode": self.row["sku"]}).json()["productId"]
            for name, kind in ((self.row["sku"] + "-N", "NUMBER"), (self.row["sku"] + "-B", "BOOLEAN")):
                r = client.post("/attributes", headers=self.owner, json={"name": name, "dataType": kind})
                self.assertEqual(r.status_code, 201, r.text)
        row = {**self.row, "attributes": self.row["sku"] + "-N:42.5;" + self.row["sku"] + "-B:TRUE"}
        result = self.submit([row], dry=False, status=201)
        self.assertEqual(result["summary"], {"categories": 0, "products": 0, "variants": 1, "attributes": 0})
        self.assertEqual(result["rows"][0]["productId"], product)
        with engine.connect() as db:
            values = list(db.execute(text("SELECT value FROM variant_attribute_values WHERE variant_id=:v ORDER BY value"),
                                    {"v": result["rows"][0]["variantId"]}).scalars())
        self.assertEqual(values, ["42.5", "true"])
        row["sku"] += "-BAD"
        row["attributes"] = self.row["sku"] + "-N:not-a-number"
        self.assertEqual(self.submit([row])["errors"][0]["code"], "INVALID_ATTRIBUTE_VALUE")

    def test_db_collation_groups_case_accents_and_duplicate_skus(self):
        first = {**self.row, "product_name": "Áo " + self.row["sku"], "category": "Màu " + self.row["sku"], "attributes": "Cỡ " + self.row["sku"] + ":M"}
        second = {**first, "product_name": first["product_name"].lower().replace("Á", "a").replace("á", "a"),
                  "category": first["category"].upper(), "attributes": "CỠ " + self.row["sku"] + ":L", "sku": self.row["sku"] + "-2"}
        preview = self.submit([first, second])
        self.assertEqual(preview["summary"], {"categories": 1, "products": 1, "variants": 2, "attributes": 1})
        second["sku"] = first["sku"].lower()
        before = self.snapshot()
        error = self.submit([first, second], dry=False, status=422)["detail"]["errors"][0]
        self.assertEqual((error["line"], error["code"]), (3, "DUPLICATE_SKU"))
        self.assertEqual(self.snapshot(), before)

    def test_duplicate_and_malformed_attribute_names_are_reported(self):
        for attributes in ("Size:M;size:L", "Size", ":M", "Size:", "Size:M;", "A:" + "x"*256):
            with self.subTest(attributes=attributes):
                error = self.submit([{**self.row, "attributes": attributes}])["errors"][0]
                self.assertEqual(error["field"], "attributes")

    def test_inactive_and_ambiguous_resources_are_rejected(self):
        with engine.begin() as db:
            category = db.execute(text("INSERT INTO categories (store_id,name,status) VALUES (:s,:n,'INACTIVE')"),
                                  {"s": self.store, "n": self.row["category"]}).lastrowid
        self.assertEqual(self.submit()["errors"][0]["code"], "INVALID_CATEGORY")
        with engine.begin() as db:
            db.execute(text("UPDATE categories SET status='ACTIVE' WHERE category_id=:c"), {"c": category})
            db.execute(text("INSERT INTO categories (store_id,name,status) VALUES (:s,:n,'ACTIVE')"),
                       {"s": self.store, "n": self.row["category"]})
        self.assertEqual(self.submit()["errors"][0]["code"], "INVALID_CATEGORY")

    def test_utf8_bom_crlf_quoted_comma_newline_and_empty_optional_fields(self):
        row = {**self.row, "product_name": "Tên, có dấu nháy \"và\" xuống\ndòng", "cost_price": "", "attributes": ""}
        content = b"\xef\xbb\xbf" + self.csv_bytes([row])
        result = self.submit(content=content, dry=False, status=201)
        with engine.connect() as db:
            record = db.execute(text("SELECT p.name,v.cost_price FROM products p JOIN product_variants v ON v.product_id=p.product_id WHERE v.variant_id=:v"),
                                {"v": result["rows"][0]["variantId"]}).one()
        self.assertEqual(record, (row["product_name"], None))
        second = {**self.row, "price": "-1"}
        bad = self.submit(content=self.csv_bytes([row, second]))
        self.assertEqual([error["line"] for error in bad["errors"] if error["field"] == "price"], [4])

    def test_invalid_headers_encoding_shapes_and_truncated_quotes(self):
        for content in (b"", b"bad,header\na,b\n", b"\xff\xfeinvalid", b"\x00", ",".join(COLUMNS).encode() + b"\nonly,2\n",
                        ",".join(COLUMNS).encode() + b'\n"unterminated', ",".join(COLUMNS).encode() + b"\n"):
            with self.subTest(content=content):
                self.assertFalse(self.submit(content=content)["valid"])
        duplicate = ",".join((*COLUMNS[:-1], "price")).encode()
        self.assertEqual(self.submit(content=duplicate)["errors"][0]["code"], "INVALID_HEADER")

    def test_numeric_limits_all_errors_and_maximum_file_size(self):
        rows = [{**self.row, "sku": self.row["sku"] + str(i), "price": value}
                for i, value in enumerate(("NaN", "Infinity", "1.001", "10000000000", "abc"))]
        result = self.submit(rows)
        self.assertEqual([error["line"] for error in result["errors"]], [2, 3, 4, 5, 6])
        self.submit(content=b"x"*(MAX_FILE_BYTES+1), status=413)

    def test_500_rows_accepted_and_501_rejected(self):
        rows = [{**self.row, "sku": self.row["sku"] + "-ROW-" + str(i)} for i in range(501)]
        self.assertEqual(self.submit(rows[:500])["summary"]["variants"], 500)
        self.assertEqual(self.submit(rows)["errors"][0]["code"], "TOO_MANY_ROWS")
        self.assertEqual(len(self.submit(rows[:500], dry=False, status=201)["rows"]), 500)

    def test_real_sql_failure_after_first_variant_rolls_back_every_table(self):
        rows = [self.row, {**self.row, "sku": self.row["sku"] + "-FAIL"}]
        before = self.snapshot()
        with engine.begin() as db:
            db.exec_driver_sql(f"""
                CREATE TRIGGER pbi111_fail_variant BEFORE INSERT ON product_variants FOR EACH ROW
                BEGIN IF NEW.sku='{rows[1]['sku']}' THEN
                    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PBI111 injected failure'; END IF; END
            """)
        try:
            self.submit(rows, dry=False, status=503)
            self.assertEqual(self.snapshot(), before)
        finally:
            with engine.begin() as db:
                db.exec_driver_sql("DROP TRIGGER pbi111_fail_variant")
        self.submit(rows, dry=False, status=201)

    def test_two_concurrent_imports_same_sku_only_one_succeeds(self):
        barrier = Barrier(2)
        content = self.csv_bytes([self.row])
        def invoke():
            barrier.wait(timeout=10)
            with TestClient(app, base_url="http://testserver/api/v1") as client:
                return client.post("/products/import-csv?dryRun=false", headers=self.owner,
                                   files={"file": ("products.csv", content, "text/csv")}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(invoke) for _ in range(2)]
            results = [future.result(timeout=30) for future in futures]
        self.assertEqual(sorted(results), [201, 422])


if __name__ == "__main__":
    unittest.main(verbosity=2)
