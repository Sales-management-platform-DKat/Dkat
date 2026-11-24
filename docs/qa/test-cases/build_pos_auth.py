"""Build the POS & Auth test-case outputs from pos_auth_cases.py.

    python docs/qa/test-cases/build_pos_auth.py        (needs openpyxl: pip install openpyxl)

- docs/qa/DKat_Test_Cases.xlsx: sheet "POS & Auth" (replaced; other sheets untouched)
- docs/qa/test-cases/pos-auth.md
- docs/qa/test-cases/issues/TC-PA-xx.md: one GitHub issue body per test case (create_issues.ps1 / .sh)
"""
import sys
from pathlib import Path

import openpyxl
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pos_auth_cases import CASES, PREPARE, SEED  # noqa: E402

XLSX = HERE.parent / "DKat_Test_Cases.xlsx"
REPO = "https://github.com/Sales-management-platform-DKat/Dkat"
SHEET = "POS & Auth"
MEMBERS = ["Tuấn", "Điền", "Quốc Anh", "Khang"]
RESULT = ["Pass", "Fail", "Chưa test", "Bị chặn"]
TRIAL = {  # how each case was tried on 25/11/2026 on fresh seed data
    "TC-PA-07": "Đạt (API)",
    "TC-PA-12": "Đạt (API bước 1-4); bước 5 giao diện chưa chạy thử",
}
HEAD_FILL = PatternFill("solid", fgColor="1F4E5F")
REQ_FILL = PatternFill("solid", fgColor="2E7D6B")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(horizontal="center", vertical="top", wrap_text=True)


def issue_search(tc_id: str) -> str:
    return f"{REPO}/issues?q=is%3Aissue+%22{tc_id}%22"


def build_sheet():
    wb = openpyxl.load_workbook(XLSX)
    if SHEET in wb.sheetnames:
        del wb[SHEET]
    ws = wb.create_sheet(SHEET, index=1)
    ws["A1"] = "Test case tích hợp POS & Auth: vòng kiểm thử Ngày 16"
    ws["A1"].font = Font(bold=True, size=14, color="1F4E5F")
    for i, line in enumerate(PREPARE, start=2):
        ws.cell(row=i, column=1, value=line).font = Font(bold=(i == 2))
    row = len(PREPARE) + 2
    ws.cell(row=row, column=1, value=f"Dữ liệu seed: {SEED['branches']}. Tồn CN01: {SEED['stock_cn01']}.").font = Font(italic=True)
    head_row = row + 2
    cols = ["ID", "Chức năng", "Tiêu đề", "Điều kiện", "Dữ liệu đầu vào (seed)", "Các bước (giao diện)", "Kiểm tra nhanh qua API",
            "Kết quả mong đợi", "Kết quả thực tế", "Pass/Fail", "Người test", "Ngày test", "Chạy thử chuẩn bị 25/11", "GitHub Issue"]
    widths = [11, 14, 30, 30, 40, 52, 40, 60, 30, 11, 12, 12, 22, 16]
    for c, (name, width) in enumerate(zip(cols, widths), start=1):
        cell = ws.cell(row=head_row, column=c, value=name)
        cell.fill = REQ_FILL if c <= 10 else HEAD_FILL
        cell.font = Font(bold=True, color="FFFFFF")
        cell.alignment, cell.border = CENTER, BORDER
        ws.column_dimensions[get_column_letter(c)].width = width
    ws.row_dimensions[head_row].height = 32
    for r, case in enumerate(CASES, start=head_row + 1):
        tc_id, func, title, cond, data, steps, api, expected, _labels = case
        values = [tc_id, func, title, cond, data, steps, api, expected, None, "Chưa test", None, None,
                  TRIAL.get(tc_id, "Đạt (API + giao diện)"), None]
        for c, v in enumerate(values, start=1):
            cell = ws.cell(row=r, column=c, value=v)
            cell.border = BORDER
            cell.alignment = CENTER if c in (1, 2, 10, 11, 12) else WRAP
        link = ws.cell(row=r, column=14, value=f"Mở issue {tc_id}")
        link.hyperlink = issue_search(tc_id)
        link.font = Font(color="0563C1", underline="single")
        ws.cell(row=r, column=12).number_format = "dd/mm/yyyy"
    first, last = head_row + 1, head_row + len(CASES)
    for rng, values, title in ((f"J{first}:J{last}", RESULT, "Pass/Fail"), (f"K{first}:K{last}", MEMBERS, "Người test")):
        dv = DataValidation(type="list", formula1='"' + ",".join(values) + '"', allow_blank=True, showErrorMessage=True,
                            errorTitle=title, error="Chọn trong danh sách: " + ", ".join(values))
        ws.add_data_validation(dv)
        dv.add(rng)
    for value, color in (("Pass", "C6E0B4"), ("Fail", "F8CBAD"), ("Bị chặn", "FFE699"), ("Chưa test", "E7E6E6")):
        ws.conditional_formatting.add(f"J{first}:J{last}", CellIsRule(operator="equal", formula=[f'"{value}"'],
                                                                      fill=PatternFill("solid", fgColor=color)))
    ws.freeze_panes = ws.cell(row=head_row + 1, column=3)
    ws.auto_filter.ref = f"A{head_row}:{get_column_letter(len(cols))}{last}"
    tally = last + 2
    ws.cell(row=tally, column=1, value="Tổng hợp").font = Font(bold=True)
    for i, res in enumerate(RESULT):
        ws.cell(row=tally + 1 + i, column=1, value=res)
        ws.cell(row=tally + 1 + i, column=2, value=f'=COUNTIF(J{first}:J{last},A{tally + 1 + i})')
    wb.save(XLSX)
    return head_row


def md_table_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", "<br>")


def build_markdown():
    lines = ["# Test case tích hợp POS & Auth (vòng kiểm thử Ngày 16)", "",
             f"Bản Excel: sheet **{SHEET}** trong [DKat_Test_Cases.xlsx](../DKat_Test_Cases.xlsx). Mỗi test case có một GitHub Issue (nhãn `test-case`, `pos-auth`).",
             "Nguồn duy nhất: [pos_auth_cases.py](pos_auth_cases.py), sinh lại bằng `python docs/qa/test-cases/build_pos_auth.py`.", "",
             "## Chuẩn bị", ""]
    lines += [f"- {line}" if not line.endswith(":") else f"**{line}**" for line in PREPARE]
    lines += ["", f"Dữ liệu seed (`python -m scripts.demo_reset`): {SEED['branches']}.", "", f"Tồn kho CN01: {SEED['stock_cn01']}.", "",
              "## Danh sách", "", "| ID | Chức năng | Tiêu đề | Issue |", "|---|---|---|---|"]
    lines += [f"| [{c[0]}](#{c[0].lower()}) | {c[1]} | {c[2]} | [tìm issue]({issue_search(c[0])}) |" for c in CASES]
    for c in CASES:
        lines += ["", f"## {c[0]}", "", f"**{c[2]}** ({c[1]})", "", body_fields(c)]
    (HERE / "pos-auth.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def body_fields(case) -> str:
    tc_id, func, title, cond, data, steps, api, expected, labels = case
    return "\n".join([
        f"| | |", "|---|---|",
        f"| **Điều kiện** | {md_table_cell(cond)} |",
        f"| **Dữ liệu đầu vào (seed)** | {md_table_cell(data)} |",
        f"| **Các bước (giao diện)** | {md_table_cell(steps)} |",
        f"| **Kiểm tra nhanh qua API** | {md_table_cell(api)} |",
        f"| **Kết quả mong đợi** | {md_table_cell(expected)} |",
        f"| **Chạy thử chuẩn bị 25/11** | {TRIAL.get(tc_id, 'Đạt (API + giao diện)')} |",
    ])


def build_issues():
    out = HERE / "issues"
    out.mkdir(exist_ok=True)
    for case in CASES:
        tc_id, func, title = case[0], case[1], case[2]
        body = "\n".join([
            f"Test case tích hợp **POS & Auth** cho vòng kiểm thử Ngày 16. Chuẩn bị chung (seed `demo_reset`, tài khoản, cửa sổ trình duyệt): "
            f"[docs/qa/test-cases/pos-auth.md]({REPO}/blob/develop/docs/qa/test-cases/pos-auth.md#chuẩn-bị).", "",
            body_fields(case), "",
            "### Khi chạy",
            "- [ ] Đã chạy `python -m scripts.demo_reset` (hoặc chạy nối tiếp các TC trước theo thứ tự)",
            "- [ ] Ghi Kết quả thực tế, Pass/Fail, Người test, Ngày test vào sheet **POS & Auth** của `docs/qa/DKat_Test_Cases.xlsx`",
            "- [ ] Fail: tạo bug trong `docs/qa/DKat_Bug_Log.xlsx`, ghi mã bug vào comment của issue này",
            "- [ ] Đóng issue khi Pass",
        ])
        (out / f"{tc_id}.md").write_text(body + "\n", encoding="utf-8")
    titles = "\n".join(f"{c[0]}\t[{c[0]}] {c[2]}\t{','.join(['test-case', 'pos-auth'] + c[8])}" for c in CASES)
    (out / "index.tsv").write_text(titles + "\n", encoding="utf-8")


if __name__ == "__main__":
    head = build_sheet()
    build_markdown()
    build_issues()
    print(f"OK: sheet '{SHEET}' ({len(CASES)} test case, header row {head}), pos-auth.md, issues/*.md")
