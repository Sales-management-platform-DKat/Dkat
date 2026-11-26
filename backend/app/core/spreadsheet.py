"""Read a small tabular upload (CSV or XLSX) into header-keyed records.

Used by stock imports. Columns are matched case-insensitively and through
Vietnamese/English aliases; unknown columns are ignored so templates can carry
reference columns such as the product name.
"""
import csv
import io
import unicodedata
import zipfile
from datetime import date, datetime
from decimal import Decimal

from app.core.csv import CsvIssue, CsvRecord, issue

XLSX_MAGIC = b"PK\x03\x04"
XLS_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
# Guard against zip bombs: a 5 MB upload may not expand past this.
MAX_XLSX_UNCOMPRESSED_BYTES = 60 * 1024 * 1024


class TableError(ValueError):
    def __init__(self, code: str, line: int, message: str):
        super().__init__(message)
        self.code = code
        self.line = line


def _fold(value: str) -> str:
    text = unicodedata.normalize("NFD", value.replace("﻿", "").strip().casefold())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn").replace("đ", "d")
    return " ".join(text.replace("_", " ").replace("-", " ").split())


def detect_kind(content: bytes, filename: str | None) -> str:
    name = (filename or "").casefold()
    if content.startswith(XLSX_MAGIC) or name.endswith(".xlsx"):
        return "xlsx"
    if content.startswith(XLS_MAGIC) or name.endswith(".xls"):
        return "xls"
    return "csv"


def _cell_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else repr(value)
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _xlsx_rows(content: bytes, limit: int):
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            if sum(item.file_size for item in archive.infolist()) > MAX_XLSX_UNCOMPRESSED_BYTES:
                raise ValueError("too large")
    except (zipfile.BadZipFile, ValueError):
        raise TableError("INVALID_FILE", 1, "Không đọc được file Excel. Hãy lưu lại dưới dạng .xlsx hoặc CSV UTF-8.") from None
    from openpyxl import load_workbook  # imported lazily: only needed for Excel uploads

    try:
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception:
        raise TableError("INVALID_FILE", 1, "Không đọc được file Excel. Hãy lưu lại dưới dạng .xlsx hoặc CSV UTF-8.") from None
    try:
        sheet = workbook.worksheets[0]
        for index, row in enumerate(sheet.iter_rows(values_only=True), start=1):
            if index > limit:
                break
            yield index, [_cell_text(value) for value in row]
    finally:
        workbook.close()


def _csv_rows(content: bytes):
    """Yield (physical start line, cells); a quoted cell may span several lines."""
    try:
        source = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise TableError(
            "INVALID_UTF8", 1,
            "File CSV phải lưu với mã hóa UTF-8 (Excel: Lưu thành → CSV UTF-8). Bạn cũng có thể tải lên file .xlsx.",
        ) from None
    if "\x00" in source:
        raise TableError("INVALID_CSV", 1, "File chứa ký tự NUL không hợp lệ")
    first_line = source.split("\n", 1)[0]
    # Excel in many locales writes ';' or tab separated "CSV".
    delimiter = max([",", ";", "\t"], key=first_line.count) if first_line else ","
    reader = csv.reader(io.StringIO(source, newline=""), delimiter=delimiter, strict=True)
    while True:
        start = reader.line_num + 1
        try:
            values = next(reader)
        except StopIteration:
            return
        except csv.Error:
            raise TableError("INVALID_CSV", start, "CSV sai dấu nháy, cấu trúc hoặc ô quá dài") from None
        yield start, values


def read_table(
    content: bytes,
    filename: str | None,
    *,
    required: tuple[str, ...],
    optional: tuple[str, ...] = (),
    aliases: dict[str, str] | None = None,
    max_rows: int,
) -> tuple[list[CsvRecord], list[CsvIssue], int, str]:
    """Return (records, errors, data_row_count, kind) with records keyed by canonical column."""
    kind = detect_kind(content, filename)
    if kind == "xls":
        return [], [issue(1, "file", "UNSUPPORTED_XLS",
                          "File .xls (Excel 97-2003) chưa được hỗ trợ. Hãy lưu lại dưới dạng .xlsx hoặc CSV UTF-8.")], 0, kind
    lookup = {_fold(name): name for name in (*required, *optional)}
    lookup.update({_fold(alias): name for alias, name in (aliases or {}).items()})

    rows = _xlsx_rows(content, max_rows + 50) if kind == "xlsx" else _csv_rows(content)
    records, errors, total = [], [], 0
    header: list[str | None] | None = None
    last_line = 0
    try:
        for line, values in rows:
            last_line = line
            if not any(str(value).strip() for value in values):
                continue
            if header is None:
                header = [lookup.get(_fold(str(value))) for value in values]
                present = [name for name in header if name]
                missing = [name for name in required if name not in present]
                if missing or len(present) != len(set(present)):
                    expected = ", ".join(required) + (" (tùy chọn: " + ", ".join(optional) + ")" if optional else "")
                    return [], [issue(line, "header", "INVALID_HEADER", "Dòng tiêu đề cần các cột: " + expected)], 0, kind
                continue
            total += 1
            if total > max_rows:
                errors.append(issue(line, "file", "TOO_MANY_ROWS", f"File chỉ được chứa tối đa {max_rows} dòng dữ liệu"))
                break
            if kind == "csv" and len(values) != len(header):
                errors.append(issue(line, "row", "COLUMN_COUNT", "Số ô không khớp với số cột tiêu đề"))
                continue
            record = {name: "" for name in (*required, *optional)}
            for position, name in enumerate(header):
                if name and position < len(values):
                    record[name] = str(values[position]).strip()
            records.append(CsvRecord(line, record))
    except TableError as error:
        field = "file" if error.code in {"INVALID_UTF8", "INVALID_FILE"} else "row"
        return records, [*errors, issue(error.line, field, error.code, str(error))], total, kind
    if header is None:
        return [], [issue(1, "file", "EMPTY_FILE", "File không có dữ liệu")], 0, kind
    if not total and not errors:
        errors.append(issue(last_line + 1, "file", "EMPTY_FILE", "File không có dòng dữ liệu"))
    return records, errors, total, kind
