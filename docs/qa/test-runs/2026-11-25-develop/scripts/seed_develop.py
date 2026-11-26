"""Seed the clean dkat_develop database ONLY through the develop API (no seed script works on develop).

Writes qa/seed_state.json with ids for the E2E test run.
"""
import json
import sys
from pathlib import Path

from e2e_lib import Http

QA = Path(__file__).parent
PW = "Dkat@12345678"
http = Http(QA / "logs" / "21_seed_requests.log")
admin_token = (QA / ".admin_token").read_text().strip()
state = {}


def must(r, *codes):
    if r.status_code not in codes:
        sys.exit(f"SEED FAILED {r.request.method} {r.request.url} -> {r.status_code} {r.text[:400]}")
    return r.json() if r.content else None


# 1. Store + subscription + OWNER (admin provisioning API)
body = must(http.call("POST", "/admin/accounts", headers={"X-Admin-Token": admin_token}, json_body={
    "shop_name": "DKat QA Develop", "plan": "basic", "subscription_months": 12,
    "owner_username": "owner01", "owner_full_name": "Chủ cửa hàng QA", "owner_password": PW,
    "owner_email": "owner01@example.com"}), 201)
print("admin/accounts ->", json.dumps(body, ensure_ascii=False)[:300])
login = must(http.call("POST", "/auth/login", json_body={"username": "owner01", "password": PW}), 200)
print("login keys ->", sorted(login))
owner = login["access_token"]

# 2. Branches CN01-CN03
branches = {}
for code, name in (("CN01", "Chi nhánh Quận 1"), ("CN02", "Chi nhánh Cầu Giấy"), ("CN03", "Chi nhánh Hải Châu")):
    b = must(http.call("POST", "/branches", owner, {"branchCode": code, "name": name, "address": f"Địa chỉ {code}", "phone": None}), 201)
    if code == "CN01":
        print("branch ->", json.dumps(b, ensure_ascii=False)[:300])
    branches[code] = b.get("branchId") or b.get("branch_id") or b.get("id") or b.get("data", {}).get("id")
state["branches"] = branches

# 3. Staff accounts
users = {}
for username, role, codes in (("manager01", "manager", ["CN01", "CN02"]), ("staff01", "staff", ["CN01"]),
                              ("locked01", "staff", ["CN01"])):
    u = must(http.call("POST", "/users", owner, {"username": username, "full_name": username, "password": PW,
                                                  "role": role, "branch_ids": [branches[c] for c in codes]}), 201)
    if username == "manager01":
        print("user ->", json.dumps(u, ensure_ascii=False)[:300])
    users[username] = u.get("id") or u.get("user_id") or u.get("employee_id")
state["users"] = users
r = http.call("PATCH", f"/users/{users['locked01']}/status", owner, {"status": "LOCKED"})
print("lock user ->", r.status_code, r.text[:200])

# 4. Catalog: category, product, 3 variants
cat = must(http.call("POST", "/categories", owner, {"name": "Áo thun"}), 201)
print("category ->", json.dumps(cat, ensure_ascii=False)[:200])
cat_id = cat.get("categoryId") or cat.get("category_id") or cat.get("id")
prod = must(http.call("POST", "/products", owner, {"categoryId": cat_id, "name": "Áo thun QA", "productCode": "QA-AO-01"}), 201)
print("product ->", json.dumps(prod, ensure_ascii=False)[:300])
prod_id = prod.get("productId") or prod.get("product_id") or prod.get("id")
variants = {}
for sku, name, price in (("QA-AO-01-S", "Size S", "150000"), ("QA-AO-01-M", "Size M", "160000"), ("QA-AO-01-L", "Size L", "170000")):
    v = must(http.call("POST", f"/products/{prod_id}/variants", owner, {"sku": sku, "variantName": name, "price": price, "costPrice": "90000"}), 201)
    if sku.endswith("S"):
        print("variant ->", json.dumps(v, ensure_ascii=False)[:300])
    variants[sku] = v.get("variantId") or v.get("variant_id") or v.get("id")
state.update(category=cat_id, product=prod_id, variants=variants)

# 5. Stock: S and M in stock at CN01 (10 each); L has no stock anywhere (pre-order item)
imp = must(http.call("POST", "/inventory/import", owner, {"branchId": branches["CN01"], "note": "Seed QA", "items": [
    {"variantId": variants["QA-AO-01-S"], "quantity": 10}, {"variantId": variants["QA-AO-01-M"], "quantity": 10}]}), 201)
print("import ->", json.dumps(imp, ensure_ascii=False)[:300])

(QA / "seed_state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
print("STATE", json.dumps(state, ensure_ascii=False))
