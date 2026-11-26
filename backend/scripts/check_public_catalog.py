"""Public catalog checks (FR-07.1 - FR-07.5) on the demo seed (python -m scripts.demo_reset). In-process, read-only.

    python -m scripts.check_public_catalog

1. No login: every /public route answers 200 without a token.
2. Allowlist: responses contain only the public fields (no cost price, quantity, reserved, product code,
   store id, status, created_*), checked on the raw JSON.
3. Filters: keyword, categoryId (with sub-categories), attr (same variant), inStock, paging, storeId.
4. Rate limit: N+1-th request in a minute -> 429 with Retry-After (limit lowered to 5 for the test).
5. Index use: EXPLAIN of the search, price/stock cards, availability and attribute queries: every big table
   (products, product_variants, inventory, preorder_items, variant_attribute_values) is read through an
   index. On a tiny database MySQL may still prefer a full scan, so the criterion is that an index is
   usable (possible_keys) and none of these tables is scanned without one; the chosen key is printed.
"""
import json
import sys

from sqlalchemy import bindparam, text

from app.core.config import settings

FORBIDDEN = ["cost", "quantity", "reserved", "allocated", "productCode", "product_code", "storeId", "store_id",
             "status", "createdAt", "created_at", "createdBy", "created_by", "barcode", "available"]
BIG_TABLES = {"products", "product_variants", "inventory", "preorder_items", "variant_attribute_values"}
ALIASES = {"p": "products", "v": "product_variants", "sv": "product_variants", "i": "inventory", "si": "inventory",
           "pi": "preorder_items", "po": "preorders", "va": "variant_attribute_values", "a": "attributes",
           "sb": "branches", "c": "categories"}
results: list[tuple[str, bool, str]] = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"\n      {detail}" if detail else ""), flush=True)


def keys_of(obj, out=None):
    out = set() if out is None else out
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.add(k)
            keys_of(v, out)
    elif isinstance(obj, list):
        for v in obj:
            keys_of(v, out)
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    settings.NOTIFY_RETRY_ENABLED = False
    from fastapi.testclient import TestClient

    from app.db.session import engine
    from app.main import app
    from app.modules.catalog import repository
    from app.modules.catalog.router import public_limiter

    public_limiter.reset()
    with TestClient(app) as c:
        get = lambda path, **params: c.get(f"/api/v1/public{path}", params=params)  # noqa: E731
        everything = get("/products", size=50).json()
        detail = get(f"/products/{everything['items'][0]['id']}").json()
        cats, branches = get("/categories").json(), get("/branches").json()
        check("Không đăng nhập vẫn gọi được 4 route", all(r.status_code == 200 for r in (
            get("/products"), get(f"/products/{everything['items'][0]['id']}"), get("/categories"), get("/branches"))))

        keys = keys_of([everything, detail, cats, branches])
        leaked = sorted(k for k in keys if any(f.lower() == k.lower() for f in FORBIDDEN))
        raw = json.dumps([everything, detail, cats, branches], ensure_ascii=False)
        check("Không có trường nội bộ (FR-07.5)", not leaked and "90000" not in raw and "AO-000" not in raw,
              f"các khóa trả về: {sorted(keys)}")
        card_keys = set(everything["items"][0])
        check("Mỗi sản phẩm: id, tên, ảnh, danh mục, khoảng giá, inStock",
              card_keys == {"id", "name", "imageUrl", "category", "priceMin", "priceMax", "inStock"}, str(sorted(card_keys)))

        with engine.connect() as db:
            expected = db.execute(text("""SELECT COUNT(*) FROM products p WHERE p.status='ACTIVE'
                AND EXISTS (SELECT 1 FROM product_variants v WHERE v.product_id=p.product_id AND v.status='ACTIVE')""")).scalar_one()
            cost_min = db.execute(text("SELECT MIN(price) FROM product_variants WHERE status='ACTIVE' AND product_id=:p"),
                                  {"p": everything["items"][0]["id"]}).scalar_one()
        check("Chỉ sản phẩm ACTIVE có biến thể ACTIVE; khoảng giá = MIN/MAX giá biến thể ACTIVE",
              everything["total"] == expected and everything["items"][0]["priceMin"] == float(cost_min),
              f"API {everything['total']} sản phẩm, SQL {expected}; priceMin {everything['items'][0]['priceMin']} = {float(cost_min)}")

        names = lambda r: [i["name"] for i in r.json()["items"]]  # noqa: E731
        kw = get("/products", keyword="jean")
        cat_id = next(x["id"] for x in cats if x["name"] == "Áo")
        by_cat = get("/products", categoryId=cat_id)
        black_m = get("/products", attr=["Màu:Đen", "Size:M"])
        out = get("/products", inStock="false")
        paged = get("/products", size=2, page=2).json()
        check("Lọc keyword / categoryId / attr (cùng biến thể) / inStock / phân trang",
              names(kw) == ["Quần jean slim"] and set(names(by_cat)) == {"Áo khoác gió DKat", "Áo thun cotton DKat"}
              and names(black_m) == ["Áo khoác gió DKat"] and out.json()["total"] == 0
              and paged["page"] == 2 and len(paged["items"]) == 2 and paged["totalPages"] == (everything["total"] + 1) // 2,
              f"jean {names(kw)}; Áo {names(by_cat)}; Đen+M {names(black_m)}; hết hàng {out.json()['total']}; trang 2/{paged['totalPages']}")
        hero = next(v for v in detail["variants"]) if detail["name"] == "Áo khoác gió DKat" else None
        check("Chi tiết: biến thể + IN_STOCK/OUT_OF_STOCK theo chi nhánh, không có số lượng",
              all(set(b) == {"branchId", "availability"} for v in detail["variants"] for b in v["branches"])
              and (hero is None or {b["availability"] for b in hero["branches"]} == {"OUT_OF_STOCK"}),
              f"{detail['name']}: " + "; ".join(f"{v['name']} {[b['availability'][0] for b in v['branches']]}" for v in detail["variants"]))
        bad = [get("/products", attr="sai").status_code, get("/products", size=51).status_code, get("/products/999999").status_code]
        check("Dữ liệu sai: attr sai định dạng 422, size > 50 422, sản phẩm không tồn tại 404", bad == [422, 422, 404], str(bad))

        saved = public_limiter.limit
        public_limiter.limit = 5
        public_limiter.reset()
        try:
            codes = [get("/categories") for _ in range(6)]
        finally:
            public_limiter.limit = saved
            public_limiter.reset()
        check("Giới hạn tốc độ: lần 6 trong 1 phút -> 429 + Retry-After (giới hạn thật: %d/phút/IP)" % saved,
              [r.status_code for r in codes] == [200] * 5 + [429] and codes[-1].headers.get("retry-after")
              and codes[0].headers.get("x-ratelimit-remaining") == "4",
              f"{[r.status_code for r in codes]}, Retry-After {codes[-1].headers.get('retry-after')}s, X-RateLimit-Remaining lần 1 = {codes[0].headers.get('x-ratelimit-remaining')}")

    # ---- EXPLAIN
    with engine.connect() as db:
        store = repository.store_ids(db)[0]
        cat_ids = [x["id"] for x in repository.categories(db, store)]
        pids = list(db.execute(text("SELECT product_id FROM products WHERE store_id=:s"), {"s": store}).scalars())
        vids = list(db.execute(text("SELECT variant_id FROM product_variants WHERE product_id IN :p")
                               .bindparams(bindparam("p", expanding=True)), {"p": pids}).scalars())
        bids = [b["branchId"] for b in repository.active_branches(db, store)]
        where, params = repository.search_statement(keyword=None, attrs=[("Màu", "Đen")], in_stock=True)
        targets = {
            "tìm kiếm (store + danh mục + attr + inStock)": (
                f"SELECT p.product_id FROM products p WHERE {where} ORDER BY p.name, p.product_id LIMIT 20",
                {**params, "s": store, "cats": cat_ids}, ["cats"]),
            "còn/hết theo chi nhánh (trang chi tiết)": (repository.AVAILABLE_PAIRS, {"vids": vids, "bids": bids}, ["vids", "bids"]),
        }
        cards_sql = f"""SELECT p.product_id,
               (SELECT MIN(v.price) FROM product_variants v WHERE v.product_id = p.product_id AND v.status = 'ACTIVE'),
               {repository.HAS_STOCK.format(p="p.product_id")}
               FROM products p WHERE p.product_id IN :ids"""
        targets["thẻ sản phẩm (khoảng giá + inStock)"] = (cards_sql, {"ids": pids}, ["ids"])
        for label, (sql, p, expanding) in targets.items():
            stmt = text("EXPLAIN " + sql).bindparams(*[bindparam(n, expanding=True) for n in expanding])
            rows = [dict(r) for r in db.execute(stmt, p).mappings()]
            plan = [(ALIASES.get(r["table"], r["table"]), r["type"], r["key"], r["possible_keys"]) for r in rows]
            scans = [(t, typ) for t, typ, key, possible in plan if t in BIG_TABLES and key is None and possible is None]
            seen = {t for t, *_ in plan}
            print(f"      {label}: " + "; ".join(f"{t} {typ}/{key or ('- (có thể dùng: ' + possible + ')' if possible else '-')}"
                                                for t, typ, key, possible in plan))
            check(f"EXPLAIN {label}: bảng lớn đều có index dùng được", not scans and bool(seen & BIG_TABLES),
                  f"bảng lớn: {sorted(seen & BIG_TABLES)}; quét không có index: {scans or 'không'}")

    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} kiểm tra đạt")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
