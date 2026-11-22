import csv
import io
from dataclasses import dataclass

from pydantic import BaseModel

MAX_FILE_BYTES = 5 * 1024 * 1024


class CsvIssue(BaseModel):
    line: int
    field: str
    code: str
    message: str


@dataclass(frozen=True)
class CsvRecord:
    line: int
    values: dict[str, str]


def issue(line: int, field: str, code: str, message: str) -> CsvIssue:
    return CsvIssue(line=line, field=field, code=code, message=message)


def read_csv(content: bytes, columns: tuple[str, ...], max_rows: int) -> tuple[list[CsvRecord], list[CsvIssue], int]:
    try:
        source = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [], [issue(1, "file", "INVALID_UTF8", "File phải được lưu dưới dạng UTF-8")], 0
    if "\x00" in source:
        return [], [issue(1, "file", "INVALID_CSV", "File chứa ký tự NUL không hợp lệ")], 0

    reader = csv.reader(io.StringIO(source, newline=""), strict=True)
    rows, errors, total = [], [], 0
    line = 1
    try:
        header = next(reader, None)
        if header is None:
            return [], [issue(1, "file", "EMPTY_FILE", "File không có dữ liệu")], 0
        header = [value.strip() for value in header]
        if len(header) != len(set(header)) or set(header) != set(columns):
            return [], [issue(1, "header", "INVALID_HEADER", "Cần đúng các cột: " + ", ".join(columns))], 0
        while True:
            line = reader.line_num + 1
            values = next(reader, None)
            if values is None:
                break
            if not any(value.strip() for value in values):
                continue
            total += 1
            if total > max_rows:
                errors.append(issue(line, "file", "TOO_MANY_ROWS", f"File chỉ được chứa tối đa {max_rows} dòng dữ liệu"))
                break
            if len(values) != len(header):
                errors.append(issue(line, "row", "COLUMN_COUNT", "Số ô không khớp với số cột tiêu đề"))
                continue
            rows.append(CsvRecord(line, dict(zip(header, values))))
    except csv.Error:
        errors.append(issue(line, "row", "INVALID_CSV", "CSV sai dấu nháy, cấu trúc hoặc ô quá dài"))
    if not total and not errors:
        errors.append(issue(line, "file", "EMPTY_FILE", "File không có dòng dữ liệu"))
    return rows, errors, total
