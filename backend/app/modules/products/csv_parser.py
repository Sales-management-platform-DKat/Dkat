import csv
import io
from dataclasses import dataclass

from pydantic import ValidationError

from app.modules.products.csv_schemas import CsvIssue, CsvProductRow

MAX_ROWS = 500
MAX_FILE_BYTES = 5 * 1024 * 1024
COLUMNS = ("product_name", "category", "variant_name", "sku", "price", "cost_price", "attributes")


@dataclass
class ParsedRow:
    line: int
    data: CsvProductRow
    attributes: list[tuple[str, str]]


def issue(line: int, field: str, code: str, message: str) -> CsvIssue:
    return CsvIssue(line=line, field=field, code=code, message=message)


def parse_csv(content: bytes) -> tuple[list[ParsedRow], list[CsvIssue], int]:
    try:
        source = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [], [issue(1, "file", "INVALID_UTF8", "File phải được lưu dưới dạng UTF-8")], 0
    if "\x00" in source:
        return [], [issue(1, "file", "INVALID_CSV", "File chứa ký tự NUL không hợp lệ")], 0
    reader = csv.reader(io.StringIO(source, newline=""), strict=True)
    rows, errors, total = [], [], 0
    try:
        header = next(reader, None)
        if header is None:
            return [], [issue(1, "file", "EMPTY_FILE", "File không có dữ liệu")], 0
        header = [value.strip() for value in header]
        if len(header) != len(set(header)) or set(header) != set(COLUMNS):
            return [], [issue(1, "header", "INVALID_HEADER", "Cần đúng các cột: " + ", ".join(COLUMNS))], 0
        while True:
            line = reader.line_num + 1
            values = next(reader, None)
            if values is None:
                break
            if not values or not any(value.strip() for value in values):
                continue
            total += 1
            if total > MAX_ROWS:
                errors.append(issue(line, "file", "TOO_MANY_ROWS", "File chỉ được chứa tối đa 500 dòng dữ liệu"))
                break
            if len(values) != len(header):
                errors.append(issue(line, "row", "COLUMN_COUNT", "Số ô không khớp với số cột tiêu đề"))
                continue
            data = dict(zip(header, values))
            data["cost_price"] = data["cost_price"].strip() or None
            try:
                row = CsvProductRow.model_validate(data)
            except ValidationError as error:
                errors.extend(issue(line, str(item["loc"][0]), "INVALID_VALUE", item["msg"]) for item in error.errors())
                continue
            attributes = []
            bad_attributes = False
            if row.attributes.strip():
                for part in row.attributes.split(";"):
                    name, separator, value = part.partition(":")
                    name, value = name.strip(), value.strip()
                    if not separator or not name or not value or len(name) > 100 or len(value) > 255:
                        errors.append(issue(line, "attributes", "INVALID_ATTRIBUTES",
                                            "Thuộc tính dùng dạng Tên:Giá trị;Tên:Giá trị, tên tối đa 100 và giá trị tối đa 255 ký tự"))
                        bad_attributes = True
                        break
                    attributes.append((name, value))
            if not bad_attributes:
                rows.append(ParsedRow(line, row, attributes))
    except csv.Error:
        errors.append(issue(max(1, reader.line_num), "row", "INVALID_CSV", "CSV sai dấu nháy, cấu trúc hoặc ô quá dài"))
    if not total and not errors:
        errors.append(issue(reader.line_num + 1, "file", "EMPTY_FILE", "File không có dòng dữ liệu"))
    return rows, errors, total
