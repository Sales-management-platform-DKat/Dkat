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
        self.assertEqual(self.client.get("/products").status_code, 401)
        self.assertEqual(self.client.get("/categories", headers={"Authorization": "Bearer bad"}).status_code, 401)
        category = self.client.post("/categories", headers=headers, json={"name": "Category"})
        self.assertEqual(category.status_code, 201, category.text)
        payload = {"categoryId": category.json()["categoryId"], "name": "Item", "productCode": "P1"}
        created = self.client.post("/products", headers=headers, json=payload)
        self.assertEqual(created.status_code, 201, created.text)
        profile = self.client.get("/api/v1/auth/me", headers=headers).json()
        self.assertEqual(created.json()["createdBy"], profile["id"])
        self.assertEqual(len(self.client.get("/products", headers=headers).json()), 1)
        for role in ("manager", "staff"):
            response = self.client.post("/api/v1/users", headers=headers, json={
                "username": role + "1", "full_name": role,
                "role": role, "password": role + "-password-123",
            })
            self.assertEqual(response.status_code, 201, response.text)
            login = self.login(role + "1:" + role, role + "-password-123")
            role_headers = {"Authorization": "Bearer " + login.json()["access_token"]}
            self.assertEqual(self.client.get("/products", headers=role_headers).status_code, 200)
            self.assertEqual(self.client.post("/products", headers=role_headers, json=payload).status_code, 403)
            self.assertEqual(self.client.post("/categories", headers=role_headers, json={"name": "Denied"}).status_code, 403)
        self.assertEqual(self.provision("owner2").status_code, 201)
        token2 = self.login("owner2", "owner-password-123").json()["access_token"]
        headers2 = {"Authorization": "Bearer " + token2}
        self.assertEqual(self.client.get("/products", headers=headers2).json(), [])
        denied = self.client.put("/products/" + str(created.json()["productId"]), headers=headers2, json={
            "categoryId": category.json()["categoryId"], "name": "Other",
        })
        self.assertEqual(denied.status_code, 404)
        with TestSession() as db:
            user = db.scalar(select(User).where(User.id == profile["id"]))
            user.status = "LOCKED"
            db.commit()
        self.assertEqual(self.client.get("/categories", headers=headers).status_code, 401)
