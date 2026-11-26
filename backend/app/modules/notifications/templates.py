"""Message texts per pre-order event (Vietnamese). SMS texts are short; core/sms removes the accents
when SMS_UNICODE=false. Placeholders come from repository.load_preorder()."""
import html
import re
from dataclasses import dataclass

EVENT_TYPES = ("PREORDER_CREATED", "PREORDER_READY", "PREORDER_CANCELLED", "PREORDER_EXPIRED")


@dataclass(frozen=True)
class Rendered:
    sms: str
    email_subject: str
    email_body: str


def _money(value) -> str:
    return f"{int(value):,}".replace(",", ".") + "đ"


def render(event_type: str, p: dict) -> Rendered:
    """p: code, customer_name, total_amount, branch_name, branch_address, branch_phone."""
    code, branch = p["code"], p["branch_name"]
    name = (p["customer_name"] or "Quý khách").strip()
    contact = f" Liên hệ: {p['branch_phone']}." if p.get("branch_phone") else ""
    greet = f"Xin chào {name},\n\n"
    sign = f"\n\nĐịa chỉ nhận hàng: {branch} - {p['branch_address']}.{contact}\n\nTrân trọng,\nDKat"

    if event_type == "PREORDER_CREATED":
        return Rendered(
            sms=f"DKat: Đã nhận đơn đặt trước {code} tại {branch}, tổng {_money(p['total_amount'])}. Chúng tôi sẽ báo khi có hàng.",
            email_subject=f"[DKat] Đã nhận đơn đặt trước {code}",
            email_body=greet + f"DKat đã nhận đơn đặt trước {code} của bạn, tổng tiền {_money(p['total_amount'])}. "
            "Chúng tôi sẽ thông báo ngay khi hàng về." + sign,
        )
    if event_type == "PREORDER_READY":
        return Rendered(
            sms=f"DKat: Đơn đặt trước {code} đã có hàng tại {branch}. Vui lòng đến nhận sớm.{contact}",
            email_subject=f"[DKat] Đơn đặt trước {code} đã có hàng",
            email_body=greet + f"Hàng trong đơn đặt trước {code} đã về. Vui lòng đến chi nhánh để nhận hàng sớm." + sign,
        )
    if event_type == "PREORDER_CANCELLED":
        return Rendered(
            sms=f"DKat: Đơn đặt trước {code} đã bị hủy.{contact}",
            email_subject=f"[DKat] Đơn đặt trước {code} đã bị hủy",
            email_body=greet + f"Đơn đặt trước {code} của bạn đã bị hủy. Nếu cần hỗ trợ, vui lòng liên hệ chi nhánh." + sign,
        )
    if event_type == "PREORDER_EXPIRED":
        return Rendered(
            sms=f"DKat: Đơn đặt trước {code} đã hết hạn nhận hàng.{contact}",
            email_subject=f"[DKat] Đơn đặt trước {code} đã hết hạn",
            email_body=greet + f"Đơn đặt trước {code} đã quá hạn nhận hàng nên đã hết hiệu lực." + sign,
        )
    raise ValueError(event_type)


# ---- FR-09.6: "goods ready" message depending on the payment status -----------------------------

TEMPLATE_READY_UNPAID = "PREORDER_READY_UNPAID"  # mẫu 1: hàng đã có, mời đến mua trước hạn giữ hàng
TEMPLATE_READY_PAID = "PREORDER_READY_PAID"  # mẫu 2: đã thanh toán, liên hệ để nhận tại cửa hàng / giao tận nơi
TEMPLATE_TYPES = (TEMPLATE_READY_UNPAID, TEMPLATE_READY_PAID)
SMS_SINGLE_PART = 160  # one GSM SMS (eSMS charges per part); accents are removed before sending


@dataclass(frozen=True)
class RenderedTemplate:
    sms: str  # Vietnamese with accents; core/sms removes them when SMS_UNICODE=false
    email_subject: str
    email_body: str  # plain text (stored in notifications.message)
    email_html: str


def ready_template_for(payment_status: str | None) -> str:
    """PAID -> mẫu 2; UNPAID / REFUNDED / unknown -> mẫu 1 (the customer still has to pay)."""
    return TEMPLATE_READY_PAID if payment_status == "PAID" else TEMPLATE_READY_UNPAID


def _first_name(full_name: str) -> str:
    """Vietnamese given name: 'Nguyễn Văn Ấn' -> 'Ấn'."""
    parts = (full_name or "").split()
    return parts[-1] if parts else ""


def _cut(text: str, limit: int) -> str:
    # "..." not "…": the ellipsis character is not in the GSM charset and would make the SMS unsendable
    return text if len(text) <= limit else text[: max(limit - 3, 1)].rstrip() + "..."


def _sms_fits(text: str) -> bool:
    from app.core.config import settings
    from app.core.sms import count_parts, remove_accents

    if settings.SMS_UNICODE:
        return count_parts(text, True) <= settings.SMS_MAX_PARTS
    return len(remove_accents(text)) <= SMS_SINGLE_PART and count_parts(remove_accents(text), False) == 1


def _sms(template_type: str, d: dict, deadline_short: str) -> str:
    """Richest variant that fits one SMS: drop / shorten name, product and branch until it fits."""
    items = d["items"]
    code, phone = d["preorder_code"], d.get("contact_phone")
    first = _first_name(d["customer_name"])
    more = f" +{len(items) - 1} SP" if len(items) > 1 else ""
    # "Chi nhánh Quận 1" -> "CN Quận 1": saves room for the customer's name and the product
    short_branch = re.sub(r"^\s*chi nhánh\s+", "CN ", d["branch_name"], flags=re.IGNORECASE)
    # (with name, product length, branch length): shorten the product first, drop the name late
    variants = [(True, 40, 40), (True, 25, 25), (True, 18, 18), (True, 12, 14), (False, 25, 25), (False, 18, 18),
                (False, 0, 18), (False, 0, 0)]
    text = ""
    for with_name, product_len, branch_len in variants:
        hello = f"Chào {_cut(first, 12)}, " if with_name and first else ""
        product = f"{_cut(items[0]['name'], product_len)} x{items[0]['quantity']}{more} " if items and product_len else ""
        order = f"(đơn {code}) " if product else f"đơn {code} "
        branch = f" tại {_cut(short_branch, branch_len)}" if branch_len else ""
        if template_type == TEMPLATE_READY_UNPAID:
            text = f"DKat: {hello}{product}{order}đã có hàng{branch}. Mời đến mua trước {deadline_short}."
        else:
            contact = f"Gọi {phone}" if phone else "Liên hệ cửa hàng"
            text = f"DKat: {hello}{product}{order}đã sẵn sàng{branch}, giữ đến {deadline_short}. {contact} để nhận tại cửa hàng/giao tận nơi."
        text = text.replace(" ,", ",").replace("  ", " ")
        if _sms_fits(text):
            return text
    return text  # the shortest variant: send_sms still enforces SMS_MAX_PARTS


def render_template(template_type: str, data: dict) -> RenderedTemplate:
    """Render mẫu 1 / mẫu 2 for both channels (FR-09.6). Pure function: no database, no sending.

    data = {
        "customer_name": "Nguyễn Văn Ấn", "preorder_code": "PD-261124-ABC",
        "branch_name": "Chi nhánh Quận 1", "branch_address": "12 Lê Lợi, Q.1", "contact_phone": "028 3822 1001",
        "hold_until": datetime  (Vietnam local time),
        "items": [{"name": "Áo sơ mi - Xanh M", "sku": "SP-02-XM", "quantity": 2, "unit_price": 250000, "line_total": 500000}],
        "total_amount": 500000,
    }
    Raises ValueError for an unknown template_type.
    """
    if template_type not in TEMPLATE_TYPES:
        raise ValueError(f"Unknown template {template_type!r}, expected one of {TEMPLATE_TYPES}")
    d = data
    name, code, branch = d["customer_name"].strip() or "Quý khách", d["preorder_code"], d["branch_name"]
    address, phone, items = d["branch_address"], d.get("contact_phone"), d["items"]
    deadline = f"{d['hold_until']:%H:%M} ngày {d['hold_until']:%d/%m/%Y}"
    deadline_short = f"{d['hold_until']:%H:%M %d/%m}"
    paid = template_type == TEMPLATE_READY_PAID
    contact_text = phone or f"{branch} ({address})"

    lines = [f"  - {i['name']} (SKU {i['sku']}) x {i['quantity']}: {_money(i['line_total'])}" for i in items]
    lines = lines or ["  (không có thông tin sản phẩm)"]
    product_block = "Sản phẩm:\n" + "\n".join(lines) + f"\nTổng tiền: {_money(d['total_amount'])} ({'đã thanh toán' if paid else 'chưa thanh toán'})"
    if paid:
        subject = f"[DKat] Đơn {code} đã sẵn sàng - chọn nhận tại cửa hàng hoặc giao tận nơi"
        body = (
            f"Xin chào {name},\n\nĐơn đặt trước {code} của bạn đã được thanh toán và hàng đã sẵn sàng.\n\n{product_block}\n\n"
            f"Vui lòng liên hệ {contact_text} để chọn cách nhận hàng:\n"
            f"  - Nhận tại cửa hàng: {branch} - {address}\n  - Giao tận nơi\n\n"
            f"Hàng được giữ cho bạn đến {deadline}.\n\nTrân trọng,\nDKat"
        )
    else:
        subject = f"[DKat] Hàng đã về - đơn {code}: mời đến mua trước {d['hold_until']:%d/%m}"
        body = (
            f"Xin chào {name},\n\nHàng trong đơn đặt trước {code} đã có tại {branch}.\n\n{product_block}\n\n"
            f"Mời bạn đến {branch} ({address}) để thanh toán và nhận hàng trước {deadline}. "
            f"Sau thời hạn này đơn hết hiệu lực và hàng được nhường cho khách khác.\n"
            f"Liên hệ: {contact_text}.\n\nTrân trọng,\nDKat"
        )

    e = html.escape  # customer name and product names come from user input
    rows = "".join(
        f"<tr><td>{e(i['name'])}</td><td>{e(i['sku'])}</td><td style='text-align:right'>{int(i['quantity'])}</td>"
        f"<td style='text-align:right'>{_money(i['line_total'])}</td></tr>"
        for i in items
    )
    table = (
        "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse'>"
        "<tr><th>Sản phẩm</th><th>SKU</th><th>SL</th><th>Thành tiền</th></tr>"
        f"{rows}<tr><td colspan='3'><b>Tổng tiền</b> ({'đã thanh toán' if paid else 'chưa thanh toán'})</td>"
        f"<td style='text-align:right'><b>{_money(d['total_amount'])}</b></td></tr></table>"
    )
    if paid:
        action = (
            f"<p>Vui lòng liên hệ <b>{e(contact_text)}</b> để chọn cách nhận hàng:</p>"
            f"<ul><li>Nhận tại cửa hàng: {e(branch)} - {e(address)}</li><li>Giao tận nơi</li></ul>"
            f"<p>Hàng được giữ cho bạn đến <b>{deadline}</b>.</p>"
        )
        intro = f"Đơn đặt trước <b>{e(code)}</b> của bạn đã được thanh toán và hàng đã sẵn sàng."
    else:
        action = (
            f"<p>Mời bạn đến <b>{e(branch)}</b> ({e(address)}) để thanh toán và nhận hàng trước <b>{deadline}</b>. "
            f"Sau thời hạn này đơn hết hiệu lực.</p><p>Liên hệ: {e(contact_text)}.</p>"
        )
        intro = f"Hàng trong đơn đặt trước <b>{e(code)}</b> đã có tại <b>{e(branch)}</b>."
    email_html = f"<p>Xin chào {e(name)},</p><p>{intro}</p>{table}{action}<p>Trân trọng,<br>DKat</p>"
    return RenderedTemplate(sms=_sms(template_type, d, deadline_short), email_subject=subject, email_body=body, email_html=email_html)
