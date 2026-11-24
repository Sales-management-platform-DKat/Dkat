"""Build the integration test-case outputs from the *_cases.py modules (one module per suite).

    python docs/qa/test-cases/build_test_cases.py        (needs openpyxl: pip install openpyxl)

For each suite (pos_auth_cases.py, preorder_notify_cases.py):
- docs/qa/DKat_Test_Cases.xlsx: its sheet (replaced; other sheets untouched)
- docs/qa/test-cases/<slug>.md
- docs/qa/test-cases/issues/<TC id>.md: one GitHub issue body per test case; issues/index.tsv lists all
  suites for create_issues.ps1 / create_issues.sh
"""
import importlib
import sys
from pathlib import Path

import openpyxl
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
SUITES = [importlib.import_module(name) for name in ("pos_auth_cases", "preorder_notify_cases")]

XLSX = HERE.parent / "DKat_Test_Cases.xlsx"
REPO = "https://github.com/Sales-management-platform-DKat/Dkat"
MEMBERS = ["Tuấn", "Điền", "Quốc Anh", "Khang"]
RESULT = ["Pass", "Fail", "Chưa test", "Bị chặn"]
HEAD_FILL = PatternFill("solid", fgColor="1F4E5F")
REQ_FILL = PatternFill("solid", fgColor="2E7D6B")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(horizontal="center", vertical="top", wrap_text=True)
COLS = ["ID", "Chức năng", "Tiêu đề", "Điều kiện", "Dữ liệu đầu vào (seed)", "Các bước (giao diện)", "Kiểm tra nhanh qua API",
        "Kết quả mong đợi", "Kết quả thực tế", "Pass/Fail", "Người test", "Ngày test", "Chạy thử chuẩn bị 25/11", "GitHub Issue"]
WIDTHS = [11, 14, 30, 30, 40, 52, 40, 64, 30, 11, 12, 12, 24, 16]


def issue_search(tc_id: str) -> str:
    return f"{REPO}/issues?q=is%3Aissue+%22{tc_id}%22"


def build_sheet(wb, suite, index):
    if suite.SHEET in wb.sheetnames:
        del wb[suite.SHEET]
    ws = wb.create_sheet(suite.SHEET, index=index)
    ws["A1"] = suite.TITLE
    ws["A1"].font = Font(bold=True, size=14, color="1F4E5F")
    for i, line in enumerate(suite.PREPARE, start=2):
        ws.cell(row=i, column=1, value=line).font = Font(bold=(i == 2))
    row = len(suite.PREPARE) + 2
    ws.cell(row=row, column=1, value=f"Dữ liệu seed: {suite.SEED['branches']}. Tồn / đơn có sẵn ở CN01: {suite.SEED['stock_cn01']}.").font = Font(italic=True)
    head = row + 2
    for c, (name, width) in enumerate(zip(COLS, WIDTHS), start=1):
        cell = ws.cell(row=head, column=c, value=name)
        cell.fill = REQ_FILL if c <= 10 else HEAD_FILL
        cell.font = Font(bold=True, color="FFFFFF")
        cell.alignment, cell.border = CENTER, BORDER
        ws.column_dimensions[get_column_letter(c)].width = width
    ws.row_dimensions[head].height = 32
    for r, case in enumerate(suite.CASES, start=head + 1):
        tc_id, func, title, cond, data, steps, api, expected, _labels = case
        result, actual = getattr(suite, "RESULTS", {}).get(tc_id, ("Chưa test", None))
        tester = getattr(suite, "RESULTS_TESTER", None) if actual else None
        when = getattr(suite, "RESULTS_DATE", None) if actual else None
        values = [tc_id, func, title, cond, data, steps, api, expected, actual, result, tester, when, suite.TRIAL[tc_id], None]
        for c, v in enumerate(values, start=1):
            cell = ws.cell(row=r, column=c, value=v)
            cell.border = BORDER
            cell.alignment = CENTER if c in (1, 2, 10, 11, 12) else WRAP
        link = ws.cell(row=r, column=14, value=f"Mở issue {tc_id}")
        link.hyperlink = issue_search(tc_id)
        link.font = Font(color="0563C1", underline="single")
        ws.cell(row=r, column=12).number_format = "dd/mm/yyyy"
    first, last = head + 1, head + len(suite.CASES)
    for rng, values, title in ((f"J{first}:J{last}", RESULT, "Pass/Fail"), (f"K{first}:K{last}", MEMBERS, "Người test")):
        dv = DataValidation(type="list", formula1='"' + ",".join(values) + '"', allow_blank=True, showErrorMessage=True,
                            errorTitle=title, error="Chọn trong danh sách: " + ", ".join(values))
        ws.add_data_validation(dv)
        dv.add(rng)
    for value, color in (("Pass", "C6E0B4"), ("Fail", "F8CBAD"), ("Bị chặn", "FFE699"), ("Chưa test", "E7E6E6")):
        ws.conditional_formatting.add(f"J{first}:J{last}", CellIsRule(operator="equal", formula=[f'"{value}"'],
                                                                      fill=PatternFill("solid", fgColor=color)))
    ws.freeze_panes = ws.cell(row=head + 1, column=3)
    ws.auto_filter.ref = f"A{head}:{get_column_letter(len(COLS))}{last}"
    tally = last + 2
    ws.cell(row=tally, column=1, value="Tổng hợp").font = Font(bold=True)
    for i, res in enumerate(RESULT):
        ws.cell(row=tally + 1 + i, column=1, value=res)
        ws.cell(row=tally + 1 + i, column=2, value=f'=COUNTIF(J{first}:J{last},A{tally + 1 + i})')
    return head


def cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", "<br>")


def fields(suite, case) -> str:
    tc_id, _func, _title, cond, data, steps, api, expected, _labels = case
    return "\n".join([
        "| | |", "|---|---|",
        f"| **Điều kiện** | {cell(cond)} |",
        f"| **Dữ liệu đầu vào (seed)** | {cell(data)} |",
        f"| **Các bước (giao diện)** | {cell(steps)} |",
        f"| **Kiểm tra nhanh qua API** | {cell(api)} |",
        f"| **Kết quả mong đợi** | {cell(expected)} |",
        f"| **Chạy thử chuẩn bị 25/11** | {cell(suite.TRIAL[tc_id])} |",
    ] + ([f"| **Kết quả vòng 2 ({suite.RESULTS_DATE})** | **{suite.RESULTS[tc_id][0]}**: {cell(suite.RESULTS[tc_id][1])} |"]
         if tc_id in getattr(suite, "RESULTS", {}) else []))


def build_markdown(suite):
    lines = [f"# {suite.TITLE}", "",
             f"Bản Excel: sheet **{suite.SHEET}** trong [DKat_Test_Cases.xlsx](../DKat_Test_Cases.xlsx). "
             f"Mỗi test case có một GitHub Issue (nhãn `test-case`, `{suite.SUITE_LABEL}`).",
             f"Nguồn duy nhất: [{suite.__name__}.py]({suite.__name__}.py), sinh lại bằng `python docs/qa/test-cases/build_test_cases.py`.", "",
             "## Chuẩn bị", ""]
    lines += [f"**{line}**" if line.endswith(":") else f"- {line}" for line in suite.PREPARE]
    lines += ["", f"Dữ liệu seed (`python -m scripts.demo_reset`): {suite.SEED['branches']}.", "",
              f"Tồn / đơn có sẵn ở CN01: {suite.SEED['stock_cn01']}.", "",
              "## Danh sách", "", "| ID | Chức năng | Tiêu đề | Issue |", "|---|---|---|---|"]
    lines += [f"| [{c[0]}](#{c[0].lower()}) | {c[1]} | {c[2]} | [tìm issue]({issue_search(c[0])}) |" for c in suite.CASES]
    for c in suite.CASES:
        lines += ["", f"## {c[0]}", "", f"**{c[2]}** ({c[1]})", "", fields(suite, c)]
    (HERE / f"{suite.SLUG}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_issues():
    out = HERE / "issues"
    out.mkdir(exist_ok=True)
    index = []
    for suite in SUITES:
        doc = f"{REPO}/blob/develop/docs/qa/test-cases/{suite.SLUG}.md"
        for case in suite.CASES:
            tc_id = case[0]
            body = "\n".join([
                f"Test case tích hợp **{suite.SHEET}** cho vòng kiểm thử Ngày 16. Chuẩn bị chung (seed `demo_reset`, tài khoản, cấu hình server): "
                f"[docs/qa/test-cases/{suite.SLUG}.md]({doc}#chuẩn-bị).", "",
                fields(suite, case), "",
                "### Khi chạy",
                "- [ ] Đã làm phần Chuẩn bị chung và các test case trước theo thứ tự",
                f"- [ ] Ghi Kết quả thực tế, Pass/Fail, Người test, Ngày test vào sheet **{suite.SHEET}** của `docs/qa/DKat_Test_Cases.xlsx`",
                "- [ ] Fail: tạo bug trong `docs/qa/DKat_Bug_Log.xlsx`, ghi mã bug vào comment của issue này",
                "- [ ] Đóng issue khi Pass",
            ])
            (out / f"{tc_id}.md").write_text(body + "\n", encoding="utf-8")
            index.append(f"{tc_id}\t[{tc_id}] {case[2]}\t{','.join(['test-case', suite.SUITE_LABEL] + case[8])}")
    (out / "index.tsv").write_text("\n".join(index) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    wb = openpyxl.load_workbook(XLSX)
    heads = [build_sheet(wb, suite, index=1 + i) for i, suite in enumerate(SUITES)]
    wb.save(XLSX)
    for suite in SUITES:
        build_markdown(suite)
    build_issues()
    print("OK: " + "; ".join(f"sheet '{s.SHEET}' {len(s.CASES)} test case (header row {h})" for s, h in zip(SUITES, heads)))
