from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.modules.auth.models import User
from sqlalchemy import select

from tests import test_auth_flow
from tests.test_auth_flow import TestSession, test_engine


class CatalogAuthTests(test_auth_flow.AuthFlowTests):
    def setUp(self):
        super().setUp()
        self.lock_patch = patch("app.modules.products.category_service.lock_store")
        self.lock_patch.start()
        self.product_lock_patch = patch("app.modules.products.service.lock_store")
        self.product_lock_patch.start()
        self.addCleanup(self.lock_patch.stop)
        self.addCleanup(self.product_lock_patch.stop)
        self.catalog_engine_patch = patch("app.modules.products.catalog_transaction.engine", test_engine)
        self.catalog_engine_patch.start()
        self.addCleanup(self.catalog_engine_patch.stop)
        with test_engine.begin() as db:
            db.exec_driver_sql("DROP TABLE IF EXISTS products")
            db.exec_driver_sql("DROP TABLE IF EXISTS categories")
            db.exec_driver_sql("""
                CREATE TABLE categories (
                    category_id INTEGER PRIMARY KEY, store_id INTEGER,
                    parent_category_id INTEGER, name TEXT, description TEXT, status TEXT
                )
            """)
            db.exec_driver_sql("""
                CREATE TABLE products (
                    product_id INTEGER PRIMARY KEY, store_id INTEGER, category_id INTEGER,
                    product_code TEXT, name TEXT, description TEXT, image_url TEXT,
                    status TEXT, created_by INTEGER, created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            db.exec_driver_sql("DROP TABLE IF EXISTS product_variants")
            db.exec_driver_sql("""
                CREATE TABLE product_variants (
                    variant_id INTEGER PRIMARY KEY, product_id INTEGER, sku TEXT,
                    variant_name TEXT, price DECIMAL, status TEXT
                )
            """)

    def test_catalog_uses_authenticated_store_role_and_creator(self):
        self.assertEqual(self.provision().status_code, 201)
        token = self.login("owner1", "owner-password-123").json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        self.assertEqual(self.client.get("/api/v1/products").status_code, 401)
        self.assertEqual(self.client.get("/api/v1/categories", headers={"Authorization": "Bearer bad"}).status_code, 401)
        category = self.client.post("/api/v1/categories", headers=headers, json={"name": "Category"})
        self.assertEqual(category.status_code, 201, category.text)
        payload = {"categoryId": category.json()["categoryId"], "name": "Item", "productCode": "P1"}
        created = self.client.post("/api/v1/products", headers=headers, json=payload)
        self.assertEqual(created.status_code, 201, created.text)
        profile = self.client.get("/api/v1/auth/me", headers=headers).json()
        self.assertEqual(created.json()["createdBy"], profile["id"])
        owner_product_list = self.client.get("/api/v1/products", headers=headers)
        self.assertEqual(owner_product_list.status_code, 200, owner_product_list.text)
        self.assertEqual(len(owner_product_list.json()), 1)
        for role in ("manager", "staff"):
            response = self.client.post("/api/v1/users", headers=headers, json={
                "username": role + "1", "full_name": role,
                "role": role, "password": role + "-password-123",
            })
            self.assertEqual(response.status_code, 201, response.text)
            login = self.login(role + "1:" + role, role + "-password-123")
            role_headers = {"Authorization": "Bearer " + login.json()["access_token"]}
            product_list = self.client.get("/api/v1/products", headers=role_headers)
            self.assertEqual(product_list.status_code, 200, product_list.text)
            self.assertEqual(self.client.post("/api/v1/products", headers=role_headers, json=payload).status_code, 403)
            self.assertEqual(self.client.post("/api/v1/categories", headers=role_headers, json={"name": "Denied"}).status_code, 403)
        self.assertEqual(self.provision("owner2").status_code, 201)
        token2 = self.login("owner2", "owner-password-123").json()["access_token"]
        headers2 = {"Authorization": "Bearer " + token2}
        self.assertEqual(self.client.get("/api/v1/products", headers=headers2).json(), [])
        denied = self.client.put("/api/v1/products/" + str(created.json()["productId"]), headers=headers2, json={
            "categoryId": category.json()["categoryId"], "name": "Other",
        })
        self.assertEqual(denied.status_code, 404)
        with TestSession() as db:
            user = db.scalar(select(User).where(User.id == profile["id"]))
            user.status = "LOCKED"
            db.commit()
        self.assertEqual(self.client.get("/api/v1/categories", headers=headers).status_code, 401)

    def test_product_cost_price_is_only_visible_to_owner(self):
        from app.modules.products.schemas import ProductDetail, VariantDetail

        self.assertEqual(self.provision().status_code, 201)
        owner_login = self.login("owner1", "owner-password-123")
        owner_headers = {"Authorization": f"Bearer {owner_login.json()['access_token']}"}
        employee = self.client.post("/api/v1/users", headers=owner_headers, json={
            "username": "staff-cost", "full_name": "Staff", "password": "staff-password-123", "role": "staff",
        })
        self.assertEqual(employee.status_code, 201, employee.text)
        employee_login = self.login("staff-cost:staff", "staff-password-123")
        employee_headers = {"Authorization": f"Bearer {employee_login.json()['access_token']}"}
        product = ProductDetail(
            categoryId=1, name="Product", productCode="P1", status="ACTIVE", createdBy=1,
            productId=1, description=None, imageUrl=None,
            variants=[VariantDetail(variant_id=1, sku="P1-1", variant_name="Default", price=100, cost_price=40, barcode=None, status="ACTIVE")],
        )
        with patch("app.modules.products.router.service.get_product_detail", return_value=product):
            owner_result = self.client.get("/api/v1/products/1", headers=owner_headers)
            employee_result = self.client.get("/api/v1/products/1", headers=employee_headers)
        self.assertEqual(owner_result.status_code, 200, owner_result.text)
        self.assertEqual(owner_result.json()["variants"][0]["cost_price"], "40")
        self.assertEqual(employee_result.status_code, 200, employee_result.text)
        self.assertIsNone(employee_result.json()["variants"][0]["cost_price"])

    def test_product_image_upload_validates_type_and_is_owner_only(self):
        from PIL import Image

        self.assertEqual(self.provision().status_code, 201)
        owner_headers = {"Authorization": "Bearer " + self.login("owner1", "owner-password-123").json()["access_token"]}
        staff = self.client.post("/api/v1/users", headers=owner_headers, json={
            "username": "image-staff", "full_name": "Staff", "password": "staff-password-123", "role": "staff",
        })
        self.assertEqual(staff.status_code, 201, staff.text)
        staff_headers = {"Authorization": "Bearer " + self.login("image-staff:staff", "staff-password-123").json()["access_token"]}
        image_bytes = BytesIO()
        Image.new("RGBA", (3, 2), (30, 80, 150, 255)).save(image_bytes, format="PNG")
        payload = image_bytes.getvalue()

        with TemporaryDirectory() as image_dir, patch("app.modules.products.image_storage.IMAGE_DIR", Path(image_dir)):
            denied = self.client.post("/api/v1/products/images", headers=staff_headers,
                                      files={"file": ("image.png", payload, "image/png")})
            self.assertEqual(denied.status_code, 403)
            bad_type = self.client.post("/api/v1/products/images", headers=owner_headers,
                                        files={"file": ("not-image.png", b"<script>alert(1)</script>", "image/png")})
            self.assertEqual(bad_type.status_code, 415, bad_type.text)
            uploaded = self.client.post("/api/v1/products/images", headers=owner_headers,
                                        files={"file": ("my-product.png", payload, "image/png")})
            self.assertEqual(uploaded.status_code, 201, uploaded.text)
            image_url = uploaded.json()["imageUrl"]
            self.assertRegex(image_url, r"^/products/images/[0-9a-f]{32}\.png$")
            fetched = self.client.get("/api/v1" + image_url)
            self.assertEqual(fetched.status_code, 200)
            self.assertEqual(fetched.headers["content-type"], "image/png")
            self.assertEqual(Image.open(BytesIO(fetched.content)).size, (3, 2))
            removed = self.client.delete("/api/v1" + image_url, headers=owner_headers)
            self.assertEqual(removed.status_code, 204)
            self.assertEqual(self.client.get("/api/v1" + image_url).status_code, 404)
