"""Check the public catalog API (FR-07.1 - FR-07.5): no login, filters, no internal fields,
rate limit and index use (EXPLAIN).

Runs the app in-process (no uvicorn needed) against the real MySQL database.
Requires:  python -m scripts.seed_auth  then  python -m scripts.seed_catalog
Run from backend/:  python -m scripts.check_public_catalog      (exit code 1 on any failure)
"""
import asyncio
import re
import sys

import httpx
from sqlalchemy import text
from sqlalchemy.dialects import mysql

from app.core.config import settings
from app.db.session import close_engine, engine, standalone_transaction
from app.main import create_app
from app.modules.catalog import repository
from app.modules.catalog.router import public_limiter

API = settings.API_V1_PREFIX
# Must never appear in a public response body (FR-07.5)
FORBIDDEN = [
    "cost", "123456", "quantity", "reserved", "allocated", "sku", "SP-MAU", "productCode", "barcode",
    "storeId", "branch", "created", "status", "password", "variantId",
]

results: list[tuple[bool, str, str]] = []


def check(name: str, passed: bool, detail: str = "") -> None:
    results.append((passed, name, detail))


def leaks(body: str) -> list[str]:
    return [w for w in FORBIDDEN if re.search(re.escape(w), body, re.IGNORECASE)]


async def load_ids() -> tuple[int, dict[str, int], dict[str, int]]:
    async with standalone_transaction() as db:
        store_id = (await db.execute(text("SELECT store_id FROM users WHERE username = 'owner01'"))).scalar()
        cats = dict((await db.execute(text("SELECT name, category_id FROM categories WHERE store_id = :s"), {"s": store_id})).all())
        prods = dict((await db.execute(text("SELECT product_code, product_id FROM products WHERE store_id = :s"), {"s": store_id})).all())
    if store_id is None or "Thời trang" not in cats or "SP-MAU-05" not in prods:
        sys.exit("Missing seed data. Run: python -m scripts.seed_auth && python -m scripts.seed_catalog")
    return store_id, cats, prods


# Per-store lookup tables with a handful of rows: MySQL rightly prefers a full scan over an index there
SMALL_LOOKUP_TABLES = ("branches", "attributes")


async def explain(store_id: int, category_ids: list[int], product_ids: list[int]) -> None:
    """Large tables (products, variants, inventory, pre-orders, attribute values) must be reached
    through an index (EXPLAIN type != ALL), and MySQL must return a real plan."""
    async with engine.connect() as conn:
        for name, stmt in repository.explain_targets(store_id, category_ids, product_ids).items():
            sql = str(stmt.compile(dialect=mysql.dialect(), compile_kwargs={"literal_binds": True}))
            rows = (await conn.execute(text("EXPLAIN " + sql))).mappings().all()
            plan = ", ".join(f"{r['table']}:{r['type']}/{r['key']}" for r in rows)
            print(f"  EXPLAIN {name}: {plan}")
            scans = [
                r["table"]
                for r in rows
                if r["table"] is None or (r["type"] == "ALL" and not str(r["table"]).startswith(SMALL_LOOKUP_TABLES))
            ]
            check(f"EXPLAIN {name}: bảng lớn đều dùng index", not scans, plan if scans else "")


async def main() -> int:
    store_id, cats, prods = await load_ids()
    p01, p02, p03 = prods["SP-MAU-01"], prods["SP-MAU-02"], prods["SP-MAU-03"]
    public_limiter.reset()
    transport = httpx.ASGITransport(app=create_app())

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:

        async def products(**params) -> tuple[httpx.Response, list[int]]:
            r = await c.get(f"{API}/public/products", params={"storeId": store_id, **params})
            ids = [p["id"] for p in r.json()["data"]["items"]] if r.status_code == 200 else []
            return r, ids

        # ---- 1. no login + no internal fields
        r, ids = await products(size=50)
        check("GET /public/products không token -> 200", r.status_code == 200, str(r.status_code))
        check("Response không chứa trường nội bộ", not leaks(r.text), f"lộ: {leaks(r.text)}")
        item = next((p for p in r.json()["data"]["items"] if p["id"] == p02), None)
        check(
            "Chỉ đúng các trường công khai",
            item is not None and set(item) == {"id", "name", "imageUrl", "category", "priceMin", "priceMax", "inStock"}
            and set(item["category"]) == {"id", "name"},
            str(sorted(item) if item else None),
        )
        check("Chỉ sản phẩm ACTIVE, danh mục hiển thị (01, 02, 03)", sorted(ids) == sorted([p01, p02, p03]), str(ids))
        check(
            "Khoảng giá bỏ qua biến thể INACTIVE (250000-280000)",
            item is not None and (item["priceMin"], item["priceMax"]) == (250000, 280000),
            str(item and (item["priceMin"], item["priceMax"])),
        )
        flags = {p["id"]: p["inStock"] for p in r.json()["data"]["items"]}
        check("inStock: tồn bị đặt trước hết -> false (03)", flags.get(p03) is False, str(flags.get(p03)))
        check("inStock: còn tồn khả dụng -> true (01, 02)", flags.get(p01) is True and flags.get(p02) is True, str(flags))

        rc = await c.get(f"{API}/public/categories", params={"storeId": store_id})
        tree = rc.json()["data"] if rc.status_code == 200 else []
        names = {n["name"]: [ch["name"] for ch in n["children"]] for n in tree}
        check("GET /public/categories không token -> 200", rc.status_code == 200, str(rc.status_code))
        check("Cây danh mục: Thời trang > Áo, Quần", names.get("Thời trang") == ["Áo", "Quần"], str(names))
        check("Ẩn danh mục INACTIVE và cả nhánh con", "Ngừng kinh doanh" not in names and "Hàng thanh lý" not in rc.text, str(list(names)))
        check("Cây danh mục không chứa trường nội bộ", not leaks(rc.text), f"lộ: {leaks(rc.text)}")

        # ---- 2. filters
        _, ids = await products(keyword="sơ mi")
        check("keyword 'sơ mi' -> 02", ids == [p02], str(ids))
        _, ids = await products(keyword="%")
        check("keyword '%' là ký tự thường -> rỗng", ids == [], str(ids))
        _, ids = await products(categoryId=cats["Thời trang"])
        check("categoryId gồm danh mục con (Thời trang -> 02, 03)", sorted(ids) == sorted([p02, p03]), str(ids))
        _, ids = await products(categoryId=cats["Áo"])
        check("categoryId=Áo -> 02 (04 INACTIVE bị loại)", ids == [p02], str(ids))
        r, ids = await products(categoryId=cats["Hàng thanh lý"])
        check("categoryId bị ẩn -> 200 rỗng", r.status_code == 200 and ids == [], str(ids))
        _, ids = await products(attr="Màu:Đỏ")
        check("attr=Màu:Đỏ -> 02", ids == [p02], str(ids))
        _, ids = await products(attr=["Màu:Xanh", "Size:M"])
        check("attr Xanh + M (cùng biến thể) -> 02", ids == [p02], str(ids))
        _, ids = await products(attr=["Màu:Xanh", "Size:L"])
        check("attr Xanh + L (khác biến thể) -> rỗng", ids == [], str(ids))
        _, ids = await products(attr=["Màu:Xanh", "Size:S"])
        check("attr chỉ khớp biến thể INACTIVE -> rỗng", ids == [], str(ids))
        _, ids = await products(attr="size:m")
        check("attr không phân biệt hoa/thường (size:m -> 01, 02, 03)", sorted(ids) == sorted([p01, p02, p03]), str(ids))
        _, ids = await products(inStock="true")
        check("inStock=true -> 01, 02", sorted(ids) == sorted([p01, p02]), str(ids))
        _, ids = await products(inStock="false")
        check("inStock=false -> 03", ids == [p03], str(ids))
        r, ids = await products(size=2, page=1)
        d = r.json()["data"]
        _, ids2 = await products(size=2, page=2)
        check(
            "Phân trang size=2: total 3, totalPages 2, trang 2 khác trang 1",
            d["total"] == 3 and d["totalPages"] == 2 and len(ids) == 2 and ids2 and not set(ids) & set(ids2),
            f"{d['total']=} {d['totalPages']=} {ids=} {ids2=}",
        )
        for params, label in [
            ({"attr": "Màu"}, "attr thiếu ':'"),
            ({"attr": ["a:1"] * 6}, "attr > 5"),
            ({"size": 51}, "size > 50"),
            ({"page": 0}, "page = 0"),
            ({"categoryId": 0}, "categoryId = 0"),
        ]:
            r = await c.get(f"{API}/public/products", params=params)
            check(f"{label} -> 422", r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR", str(r.status_code))

        # ---- 3. rate limit (budget shared by all /public routes)
        public_limiter.reset()
        limit = settings.PUBLIC_RATE_LIMIT_PER_MINUTE
        statuses, remaining = [], []
        for i in range(limit):
            r = await c.get(f"{API}/public/categories" if i % 2 else f"{API}/public/products")
            statuses.append(r.status_code)
            remaining.append(int(r.headers.get("X-RateLimit-Remaining", -1)))
        check(f"{limit} request đầu -> 200", set(statuses) == {200}, str(set(statuses)))
        check("X-RateLimit-Remaining giảm dần về 0", remaining[0] == limit - 1 and remaining[-1] == 0, f"{remaining[0]}..{remaining[-1]}")
        r = await c.get(f"{API}/public/products")
        check(
            f"Request thứ {limit + 1} -> 429 RATE_LIMIT_EXCEEDED + Retry-After",
            r.status_code == 429 and r.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED" and int(r.headers.get("Retry-After", 0)) > 0,
            f"{r.status_code} Retry-After={r.headers.get('Retry-After')}",
        )
        r = await c.get(f"{API}/health")
        check("Route không công khai không bị giới hạn chung", r.status_code == 200, str(r.status_code))
        public_limiter.reset()

    # ---- 4. index use
    await explain(store_id, [cats["Thời trang"], cats["Áo"], cats["Quần"]], [p01, p02, p03])
    await close_engine()

    width = max(len(n) for _, n, _ in results)
    for passed, name, detail in results:
        print(f"  {'PASS' if passed else 'FAIL'}  {name.ljust(width)}  {'' if passed else detail}")
    failed = sum(not p for p, _, _ in results)
    print(f"\n{len(results) - failed}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(asyncio.run(main()))
