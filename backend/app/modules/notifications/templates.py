"""Message texts per pre-order event (Vietnamese). SMS texts are short; core/sms removes the accents
when SMS_UNICODE=false. Placeholders come from repository.load_preorder()."""
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
