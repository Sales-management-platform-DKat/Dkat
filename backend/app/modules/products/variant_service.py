import re
from decimal import Decimal

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from app.modules.products.catalog_transaction import CatalogConflict, CatalogInvalid, CatalogNotFound
from app.modules.products.category_service import lock_store
from app.modules.products.codes import generate_sku
from app.modules.products.schemas import AttributeDataType, ProductStatus, VariantAttribute, VariantDetail
from app.modules.products.variant_schemas import AttributeInput, AttributeRecord, VariantInput

NUMBER_VALUE = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")


def list_attributes(db: Connection, store_id: int) -> list[AttributeRecord]:
    rows = db.execute(
        text("""
            SELECT attribute_id AS attributeId, name, data_type AS dataType, status
            FROM attributes WHERE store_id = :store
            ORDER BY name, attribute_id
        """),
        {"store": store_id},
    ).mappings()
    return [AttributeRecord.model_validate(row) for row in rows]


def create_attribute(db: Connection, store_id: int, data: AttributeInput) -> AttributeRecord:
    lock_store(db, store_id)
    result = db.execute(
        text("""
            INSERT INTO attributes (store_id, name, data_type, status)
            VALUES (:store, :name, :dataType, 'ACTIVE')
        """),
        {**data.model_dump(), "store": store_id},
    )
    return AttributeRecord(**data.model_dump(), attributeId=result.lastrowid, status="ACTIVE")


def list_variant_details(
    db: Connection, store_id: int, product_id: int, *, variant_id: int | None = None
) -> list[VariantDetail]:
    rows = db.execute(
        text("""
            SELECT v.variant_id, v.sku, v.variant_name, v.price, v.cost_price, v.barcode, v.status,
                   a.attribute_id, a.name, a.data_type, av.value
            FROM product_variants AS v
            JOIN products AS p ON p.product_id = v.product_id AND p.store_id = :store
            LEFT JOIN variant_attribute_values AS av ON av.variant_id = v.variant_id
            LEFT JOIN attributes AS a ON a.attribute_id = av.attribute_id AND a.store_id = :store
            WHERE v.product_id = :product AND (:variant IS NULL OR v.variant_id = :variant)
            ORDER BY v.variant_id, a.attribute_id
        """),
        {"store": store_id, "product": product_id, "variant": variant_id},
    ).mappings()
    variants: dict[int, VariantDetail] = {}
    for row in rows:
        variant = variants.get(row["variant_id"])
        if variant is None:
            variant = VariantDetail.model_validate(row)
            variants[variant.variant_id] = variant
        if row["attribute_id"] is not None:
            variant.attributes.append(VariantAttribute.model_validate(row))
    return list(variants.values())


def variant_product_id(db: Connection, store_id: int, variant_id: int) -> int:
    product_id = db.execute(
        text("""
            SELECT v.product_id FROM product_variants AS v
            JOIN products AS p ON p.product_id = v.product_id
            WHERE p.store_id = :store AND v.variant_id = :variant
        """),
        {"store": store_id, "variant": variant_id},
    ).scalar_one_or_none()
    if product_id is None:
        raise CatalogNotFound("Variant not found")
    return product_id


def normalize_value(value: str | bool | Decimal, data_type: AttributeDataType) -> str:
    if data_type == "TEXT" and isinstance(value, str) and value.strip():
        return value
    if data_type == "BOOLEAN":
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
            return value.strip().lower()
    if data_type == "NUMBER" and not isinstance(value, bool):
        number = str(value).strip()
        if len(number) <= 255 and NUMBER_VALUE.fullmatch(number):
            return number
    raise CatalogInvalid(f"Invalid {data_type} attribute value")


def attribute_values(db: Connection, store_id: int, data: VariantInput) -> list[dict]:
    if not data.attributes:
        return []
    ids = [item.attributeId for item in data.attributes]
    rows = db.execute(
        text("""
            SELECT attribute_id, data_type FROM attributes
            WHERE store_id = :store AND attribute_id IN :ids
        """).bindparams(bindparam("ids", expanding=True)),
        {"store": store_id, "ids": ids},
    ).all()
    types = dict(rows)
    if len(types) != len(ids):
        raise CatalogNotFound("Attribute not found")
    return [
        {"attribute": item.attributeId, "value": normalize_value(item.value, types[item.attributeId])}
        for item in data.attributes
    ]


def insert_variant(db: Connection, params: dict, generated_sku: str | None) -> int:
    sequence = 1
    while True:
        if generated_sku is not None:
            suffix = f"-{sequence}" if sequence > 1 else ""
            params["sku"] = generated_sku[:80 - len(suffix)].rstrip("-") + suffix
        try:
            return db.execute(
                text("""
                    INSERT INTO product_variants (product_id, sku, variant_name, price, cost_price, barcode, status)
                    VALUES (:product, :sku, :variantName, :price, :costPrice, :barcode, 'ACTIVE')
                """),
                params,
            ).lastrowid
        except IntegrityError as error:
            if getattr(error.orig, "args", ())[:1] != (1062,):
                raise
            if generated_sku is None:
                raise CatalogConflict("DUPLICATE_SKU") from error
            sequence += 1


def save_variant(
    db: Connection, store_id: int, data: VariantInput, *,
    product_id: int | None = None, variant_id: int | None = None,
) -> VariantDetail:
    lock_store(db, store_id)
    creating = variant_id is None
    if creating:
        product_code = db.execute(
            text("SELECT product_code FROM products WHERE store_id = :store AND product_id = :product"),
            {"store": store_id, "product": product_id},
        ).scalar_one_or_none()
        if product_code is None:
            raise CatalogNotFound("Product not found")
    else:
        product_id = variant_product_id(db, store_id, variant_id)

    values = attribute_values(db, store_id, data)
    params = {**data.model_dump(exclude={"attributes"}), "product": product_id, "variant": variant_id}
    if creating:
        generated_sku = None
        if data.sku is None:
            sorted_values = sorted(values, key=lambda item: item["attribute"])
            generated_sku = generate_sku(
                product_code, (item["value"] for item in sorted_values),
            )
        variant_id = insert_variant(db, params, generated_sku)
    else:
        try:
            db.execute(
                text("""
                    UPDATE product_variants SET sku = COALESCE(:sku, sku), variant_name = :variantName,
                        price = :price, cost_price = :costPrice, barcode = :barcode
                    WHERE variant_id = :variant
                """),
                params,
            )
        except IntegrityError as error:
            if getattr(error.orig, "args", ())[:1] == (1062,):
                raise CatalogConflict("DUPLICATE_SKU") from error
            raise

        db.execute(
            text("DELETE FROM variant_attribute_values WHERE variant_id = :variant"),
            {"variant": variant_id},
        )
    if values:
        db.execute(
            text("""
                INSERT INTO variant_attribute_values (variant_id, attribute_id, value)
                VALUES (:variant, :attribute, :value)
            """),
            [{"variant": variant_id, **value} for value in values],
        )
    if creating:
        db.execute(
            text("""
                INSERT INTO inventory (branch_id, variant_id, quantity)
                SELECT branch_id, :variant, 0 FROM branches
                WHERE store_id = :store AND status = 'ACTIVE'
            """),
            {"variant": variant_id, "store": store_id},
        )
    return list_variant_details(db, store_id, product_id, variant_id=variant_id)[0]


def current_cost_price(db: Connection, store_id: int, variant_id: int) -> Decimal | None:
    variant_product_id(db, store_id, variant_id)
    return db.execute(
        text("SELECT cost_price FROM product_variants WHERE variant_id = :variant"),
        {"variant": variant_id},
    ).scalar_one()


def change_variant_status(db: Connection, store_id: int, variant_id: int, status: ProductStatus) -> VariantDetail:
    lock_store(db, store_id)
    product_id = variant_product_id(db, store_id, variant_id)
    db.execute(
        text("UPDATE product_variants SET status = :status WHERE variant_id = :variant"),
        {"variant": variant_id, "status": status},
    )
    return list_variant_details(db, store_id, product_id, variant_id=variant_id)[0]
