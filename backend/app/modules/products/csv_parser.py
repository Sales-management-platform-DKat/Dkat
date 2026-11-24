from dataclasses import dataclass

from pydantic import ValidationError

from app.core.csv import MAX_FILE_BYTES as MAX_FILE_BYTES
from app.core.csv import CsvIssue, issue, read_csv
from app.modules.products.csv_schemas import CsvProductRow

MAX_ROWS = 500
COLUMNS = ("product_name", "category", "variant_name", "sku", "price", "cost_price", "attributes")


@dataclass
class ParsedRow:
    line: int
    data: CsvProductRow
    attributes: list[tuple[str, str]]


def parse_csv(content: bytes) -> tuple[list[ParsedRow], list[CsvIssue], int]:
    records, errors, total = read_csv(content, COLUMNS, MAX_ROWS)
    rows = []
    for record in records:
        line = record.line
        data = {**record.values, "cost_price": record.values["cost_price"].strip() or None}
        try:
            row = CsvProductRow.model_validate(data)
        except ValidationError as error:
            errors.extend(issue(line, str(item["loc"][0]), "INVALID_VALUE", item["msg"]) for item in error.errors())
            continue
        attributes = []
        parts = row.attributes.split(";") if row.attributes.strip() else []
        for part in parts:
            name, separator, value = part.partition(":")
            name, value = name.strip(), value.strip()
            if not separator or not name or not value or len(name) > 100 or len(value) > 255:
                errors.append(issue(line, "attributes", "INVALID_ATTRIBUTES",
                                    "Thuộc tính dùng dạng Tên:Giá trị;Tên:Giá trị, tên tối đa 100 và giá trị tối đa 255 ký tự"))
                break
            attributes.append((name, value))
        else:
            rows.append(ParsedRow(line, row, attributes))
    return rows, errors, total
