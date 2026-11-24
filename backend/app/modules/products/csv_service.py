from dataclasses import dataclass
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.core.csv import issue
from app.core.permissions import Actor
from app.db.collation import column_collation
from app.modules.products import category_service, service, variant_service
from app.modules.products.catalog_transaction import CatalogConflict, CatalogInvalid, CatalogNotFound
from app.modules.products.category_schemas import CategoryInput
from app.modules.products.csv_parser import ParsedRow, parse_csv
from app.modules.products.csv_schemas import CsvImportResult, ImportedCsvRow, ImportCounts
from app.modules.products.schemas import ProductCreate
from app.modules.products.variant_schemas import AttributeInput, AttributeValueInput, VariantInput


@dataclass
class Resource:
    name: str
    id: int | None = None
    data_type: str = "TEXT"


def collation_keys(db: Connection, values: list[str], table: str, column: str) -> dict[str, int]:
    """Group CSV names exactly as the destination column does, including accents/case."""
    values = list(dict.fromkeys(values))
    if not values:
        return {}
    collation = column_collation(db, table, column)
    params = {f"v{i}": value for i, value in enumerate(values)}
    source = " UNION ALL ".join(f"SELECT {i} AS n, :v{i} AS value" for i in range(len(values)))
    ranks = db.execute(text(f"""
        SELECT n, DENSE_RANK() OVER (ORDER BY value COLLATE {collation}) AS bucket
        FROM ({source}) AS names
    """), params)
    return {values[index]: bucket for index, bucket in ranks}


def prepare_import(db: Connection, actor: Actor, rows: list[ParsedRow], errors: list):
    category_keys = collation_keys(db, [row.data.category for row in rows], "categories", "name")
    product_keys = collation_keys(db, [row.data.product_name for row in rows], "products", "name")
    sku_keys = collation_keys(db, [row.data.sku for row in rows], "product_variants", "sku")
    attribute_keys = collation_keys(db, [name for row in rows for name, _ in row.attributes], "attributes", "name")
    categories, products, attributes, skus = {}, {}, {}, {}
    invalid_categories, invalid_products, invalid_attributes = {}, {}, {}

    for row in rows:
        data, line = row.data, row.line
        sku_key = sku_keys[data.sku]
        if sku_key in skus:
            errors.append(issue(line, "sku", "DUPLICATE_SKU", f"SKU trùng dòng {skus[sku_key]} trong file"))
        else:
            skus[sku_key] = line
        # Global SKU uniqueness applies across stores; never disclose the owning store.
        if db.execute(text("SELECT 1 FROM product_variants WHERE sku=:sku LIMIT 1"), {"sku": data.sku}).first():
            errors.append(issue(line, "sku", "DUPLICATE_SKU", "SKU đã tồn tại"))

        category_key = category_keys[data.category]
        if category_key not in categories and category_key not in invalid_categories:
            found = db.execute(text("SELECT category_id,status FROM categories WHERE store_id=:s AND name=:name"),
                               {"s": actor.store_id, "name": data.category}).all()
            if len(found) > 1:
                invalid_categories[category_key] = "Có nhiều danh mục cùng tên; cần đặt tên phân biệt trước khi import"
            elif found and found[0].status != "ACTIVE":
                invalid_categories[category_key] = "Danh mục đang ngừng hoạt động"
            else:
                categories[category_key] = Resource(data.category, found[0].category_id if found else None)
        if category_key in invalid_categories:
            errors.append(issue(line, "category", "INVALID_CATEGORY", invalid_categories[category_key]))
        else:
            product_key = (category_key, product_keys[data.product_name])
            if product_key not in products and product_key not in invalid_products:
                category = categories[category_key]
                found = db.execute(text("""
                    SELECT product_id,status FROM products WHERE store_id=:s AND category_id=:c AND name=:name
                """), {"s": actor.store_id, "c": category.id, "name": data.product_name}).all() if category.id else []
                if len(found) > 1:
                    invalid_products[product_key] = "Có nhiều sản phẩm cùng tên trong danh mục"
                elif found and found[0].status != "ACTIVE":
                    invalid_products[product_key] = "Sản phẩm đang ngừng hoạt động"
                else:
                    products[product_key] = Resource(data.product_name, found[0].product_id if found else None)
            if product_key in invalid_products:
                errors.append(issue(line, "product_name", "INVALID_PRODUCT", invalid_products[product_key]))

        seen_attributes = set()
        for name, value in row.attributes:
            key = attribute_keys[name]
            if key in seen_attributes:
                errors.append(issue(line, "attributes", "DUPLICATE_ATTRIBUTE", "Một thuộc tính xuất hiện nhiều lần trong cùng biến thể"))
                continue
            seen_attributes.add(key)
            if key not in attributes and key not in invalid_attributes:
                found = db.execute(text("SELECT attribute_id,data_type,status FROM attributes WHERE store_id=:s AND name=:name"),
                                   {"s": actor.store_id, "name": name}).all()
                if len(found) > 1:
                    invalid_attributes[key] = "Có nhiều thuộc tính cùng tên; cần đặt tên phân biệt trước khi import"
                elif found and found[0].status != "ACTIVE":
                    invalid_attributes[key] = "Thuộc tính đang ngừng hoạt động"
                else:
                    attributes[key] = Resource(name, found[0].attribute_id if found else None,
                                               found[0].data_type if found else "TEXT")
            if key in invalid_attributes:
                errors.append(issue(line, "attributes", "INVALID_ATTRIBUTE", invalid_attributes[key]))
            else:
                try:
                    variant_service.normalize_value(value, attributes[key].data_type)
                except CatalogInvalid as error:
                    errors.append(issue(line, "attributes", "INVALID_ATTRIBUTE_VALUE", str(error)))
    return categories, products, attributes, category_keys, product_keys, attribute_keys


def import_products(db: Connection, actor: Actor, content: bytes, dry_run: bool) -> CsvImportResult:
    rows, errors, total = parse_csv(content)
    if not dry_run:
        category_service.lock_store(db, actor.store_id)
    categories, products, attributes, cat_keys, prod_keys, attr_keys = prepare_import(db, actor, rows, errors)
    errors.sort(key=lambda item: (item.line, item.field, item.code))
    valid_rows = max(0, total - len({error.line for error in errors if error.line > 1}))
    if errors:
        result = CsvImportResult(dryRun=dry_run, valid=False, totalRows=total, validRows=valid_rows, errors=errors, rows=[])
        if not dry_run:
            raise HTTPException(422, {"code": "INVALID_PRODUCT_CSV", **result.model_dump(mode="json")})
        return result
    summary = ImportCounts(categories=sum(item.id is None for item in categories.values()),
                           products=sum(item.id is None for item in products.values()), variants=len(rows),
                           attributes=sum(item.id is None for item in attributes.values()))
    result = CsvImportResult(dryRun=dry_run, valid=True, totalRows=total, validRows=total, summary=summary, errors=[], rows=[])
    if dry_run:
        return result
    for row in rows:
        data = row.data
        category = categories[cat_keys[data.category]]
        product = products[(cat_keys[data.category], prod_keys[data.product_name])]
        try:
            if category.id is None:
                category.id = category_service.save_category(db, actor.store_id, CategoryInput(name=category.name)).categoryId
            if product.id is None:
                product.id = service.create_product(db, actor.store_id, actor.user_id, ProductCreate(
                    name=product.name, categoryId=category.id, productCode="CSV-" + uuid4().hex.upper(),
                )).productId
            values = []
            for name, value in row.attributes:
                attribute = attributes[attr_keys[name]]
                if attribute.id is None:
                    attribute.id = variant_service.create_attribute(db, actor.store_id,
                        AttributeInput(name=attribute.name, dataType="TEXT")).attributeId
                values.append(AttributeValueInput(attributeId=attribute.id, value=value))
            variant = variant_service.save_variant(db, actor.store_id, VariantInput(
                sku=data.sku, variantName=data.variant_name, price=data.price, costPrice=data.cost_price, attributes=values,
            ), product_id=product.id)
        except (CatalogConflict, CatalogInvalid, CatalogNotFound) as error:
            raise HTTPException(422, {"code": "INVALID_PRODUCT_CSV", "errors": [
                issue(row.line, "sku" if str(error) == "DUPLICATE_SKU" else "row", "IMPORT_CONFLICT", str(error)).model_dump(),
            ]}) from None
        result.rows.append(ImportedCsvRow(line=row.line, productId=product.id, variantId=variant.variant_id, sku=variant.sku))
    return result
