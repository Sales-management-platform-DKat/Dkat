"""Tests for notifications.templates.render_template (FR-09.6): 2 templates x 2 channels.

Pure functions, no database or sending. Prints the 4 rendered messages, then checks:
customer name, products + quantities, branch, hold deadline, payment wording, SMS fits one part
(and stays sendable through core/sms), HTML escaping, template choice by payment status.
Run from backend/:  python -m scripts.check_templates      (exit code 1 on any failure)
"""
import sys
from datetime import datetime

from app.core.config import settings
from app.core.sms import count_parts, prepare_content, remove_accents
from app.modules.notifications.service import hold_until_vn
from app.modules.notifications.templates import (
    TEMPLATE_READY_PAID,
    TEMPLATE_READY_UNPAID,
    ready_template_for,
    render_template,
)

results: list[tuple[bool, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((bool(ok), name, detail))


HOLD = datetime(2026, 12, 1, 21, 30)  # Vietnam time
DATA = {
    "customer_name": "Nguyễn Văn Ấn",
    "preorder_code": "PD-261124-A1B2",
    "branch_name": "Chi nhánh Quận 1",
    "branch_address": "12 Lê Lợi, Q.1, TP.HCM",
    "contact_phone": "028 3822 1001",
    "hold_until": HOLD,
    "items": [
        {"name": "Áo sơ mi mẫu - Xanh M", "sku": "SP-MAU-02-XANH-M", "quantity": 2, "unit_price": 250000, "line_total": 500000},
        {"name": "Quần kaki mẫu - Đen M", "sku": "SP-MAU-03-M", "quantity": 1, "unit_price": 300000, "line_total": 300000},
    ],
    "total_amount": 800000,
}


def sms_ok(text: str) -> bool:
    """Fits one GSM part after accents are removed AND core/sms accepts it."""
    sent, error = prepare_content(text, False)
    return error is None and len(remove_accents(text)) <= 160 and count_parts(sent, False) == 1


def main() -> int:
    settings.SMS_UNICODE = False
    unpaid = render_template(TEMPLATE_READY_UNPAID, DATA)
    paid = render_template(TEMPLATE_READY_PAID, DATA)

    for title, r in (("MẪU 1 - CHƯA THANH TOÁN", unpaid), ("MẪU 2 - ĐÃ THANH TOÁN", paid)):
        print(f"===== {title}")
        print(f"[SMS] ({len(remove_accents(r.sms))} ký tự sau khi bỏ dấu)\n{r.sms}\n  -> gửi đi: {prepare_content(r.sms, False)[0]}")
        print(f"[EMAIL] Tiêu đề: {r.email_subject}\n{r.email_body}\n")

    # ---- mẫu 1: chưa thanh toán
    s, b = unpaid.sms, unpaid.email_body
    check("Mẫu 1 SMS: tên khách, sản phẩm, chi nhánh, hạn giữ hàng",
          "Ấn" in s and "Áo sơ mi mẫu - Xanh M x2" in s and "CN Quận 1" in s and "Mời đến mua trước 21:30 01/12" in s, s)
    check("Mẫu 1 SMS: có số SP khác (+1 SP) và mã đơn", "+1 SP" in s and "PD-261124-A1B2" in s, s)
    check("Mẫu 1 email: tên đầy đủ, chi nhánh + địa chỉ, hạn giữ hàng đầy đủ",
          "Xin chào Nguyễn Văn Ấn" in b and "Chi nhánh Quận 1 (12 Lê Lợi, Q.1, TP.HCM)" in b and "trước 21:30 ngày 01/12/2026" in b, b)
    check("Mẫu 1 email: đủ danh sách sản phẩm + số lượng + tổng, ghi chưa thanh toán",
          "Áo sơ mi mẫu - Xanh M (SKU SP-MAU-02-XANH-M) x 2: 500.000đ" in b and "Quần kaki mẫu - Đen M (SKU SP-MAU-03-M) x 1: 300.000đ" in b
          and "Tổng tiền: 800.000đ (chưa thanh toán)" in b, b)
    check("Mẫu 1 email: tiêu đề có mã đơn và hạn", unpaid.email_subject == "[DKat] Hàng đã về - đơn PD-261124-A1B2: mời đến mua trước 01/12", unpaid.email_subject)

    # ---- mẫu 2: đã thanh toán
    s, b = paid.sms, paid.email_body
    check("Mẫu 2 SMS: tên khách, sản phẩm (cắt cho vừa 1 tin), chi nhánh, hạn giữ, SĐT cửa hàng, 2 cách nhận",
          "Chào Ấn" in s and "Áo sơ mi" in s and "x2 +1 SP" in s and "CN Quận 1" in s and "giữ đến 21:30 01/12" in s
          and "028 3822 1001" in s and "nhận tại cửa hàng/giao tận nơi" in s, s)
    check("Mẫu 2 email: tên, đã thanh toán, SĐT, nhận tại cửa hàng (chi nhánh + địa chỉ) / giao tận nơi, hạn giữ",
          "Xin chào Nguyễn Văn Ấn" in b and "đã được thanh toán" in b and "liên hệ 028 3822 1001" in b
          and "Nhận tại cửa hàng: Chi nhánh Quận 1 - 12 Lê Lợi, Q.1, TP.HCM" in b and "Giao tận nơi" in b and "đến 21:30 ngày 01/12/2026" in b, b)
    check("Mẫu 2 email: đủ sản phẩm + số lượng, tổng (đã thanh toán)",
          "x 2: 500.000đ" in b and "x 1: 300.000đ" in b and "Tổng tiền: 800.000đ (đã thanh toán)" in b, b)

    # ---- HTML
    for label, r in (("Mẫu 1", unpaid), ("Mẫu 2", paid)):
        h = r.email_html
        check(f"{label} HTML: bảng sản phẩm (tên, SKU, SL, thành tiền) và tổng",
              "<table" in h and "Áo sơ mi mẫu - Xanh M</td><td>SP-MAU-02-XANH-M</td><td style='text-align:right'>2</td>" in h and "800.000đ" in h, h[:200])
    evil = {**DATA, "customer_name": "<script>alert(1)</script>", "items": [{**DATA["items"][0], "name": "<b>x</b>"}]}
    h = render_template(TEMPLATE_READY_PAID, evil).email_html
    check("HTML escape tên khách / tên sản phẩm (chặn chèn mã)", "<script>" not in h and "&lt;script&gt;" in h and "&lt;b&gt;x&lt;/b&gt;" in h, h[:200])

    # ---- SMS length: always one GSM part and sendable
    for label, r in (("Mẫu 1", unpaid), ("Mẫu 2", paid)):
        check(f"{label} SMS: 1 tin (<= 160 ký tự không dấu) và core/sms gửi được", sms_ok(r.sms), f"{len(remove_accents(r.sms))}: {r.sms}")
    long_data = {
        **DATA,
        "customer_name": "Tôn Nữ Hoàng Phương Thảo Nguyên Khánh",
        "preorder_code": "PD-261124-9F1C2A7B3D4E5F60718293A4B5C6D7E8",  # pre-order module style: 42 characters
        "branch_name": "Chi nhánh Trung tâm Thương mại Vincom Bà Triệu Hai Bà Trưng",
        "items": [{"name": "Áo khoác gió hai lớp chống nước phiên bản giới hạn mùa đông", "sku": "X", "quantity": 12,
                   "unit_price": 1, "line_total": 12}] * 5,
        "contact_phone": "0236 382 1003",
    }
    for t in (TEMPLATE_READY_UNPAID, TEMPLATE_READY_PAID):
        r = render_template(t, long_data)
        check(f"{t}: tên/chi nhánh/sản phẩm/mã đơn rất dài -> vẫn 1 tin, gửi được, còn mã đơn + hạn",
              sms_ok(r.sms) and long_data["preorder_code"] in r.sms and "01/12" in r.sms, f"{len(remove_accents(r.sms))}: {r.sms}")
    r = render_template(TEMPLATE_READY_PAID, {**DATA, "contact_phone": None})
    check("Không có SĐT: SMS ghi 'Liên hệ cửa hàng', email ghi chi nhánh + địa chỉ",
          "Liên hệ cửa hàng" in r.sms and "liên hệ Chi nhánh Quận 1 (12 Lê Lợi, Q.1, TP.HCM)" in r.email_body, r.sms)

    # ---- choice and helpers
    check("PAID -> mẫu 2; UNPAID / REFUNDED / None -> mẫu 1",
          (ready_template_for("PAID"), ready_template_for("UNPAID"), ready_template_for("REFUNDED"), ready_template_for(None))
          == (TEMPLATE_READY_PAID, TEMPLATE_READY_UNPAID, TEMPLATE_READY_UNPAID, TEMPLATE_READY_UNPAID))
    try:
        render_template("PREORDER_SOMETHING", DATA)
        check("Mẫu không tồn tại -> ValueError", False, "no error")
    except ValueError:
        check("Mẫu không tồn tại -> ValueError", True)
    check("Hạn giữ hàng: expires_at (UTC) -> giờ Việt Nam (+7)",
          hold_until_vn({"expires_at": datetime(2026, 12, 1, 14, 30), "ready_at": None}) == datetime(2026, 12, 1, 21, 30))
    settings.PREORDER_READY_DAYS = 7
    check("Chưa có expires_at: ready_at + PREORDER_READY_DAYS, đổi sang giờ Việt Nam",
          hold_until_vn({"expires_at": None, "ready_at": datetime(2026, 11, 24, 3, 0)}) == datetime(2026, 12, 1, 10, 0))

    width = max(len(n) for _, n, _ in results)
    for ok, name, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {'' if ok else detail}")
    failed = sum(not ok for ok, _, _ in results)
    print(f"\n{len(results) - failed}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
