"""Call NotificationService.notify_preorder for real (FR-09.1 - FR-09.4) and show the notifications rows.

Run from backend/:
    python -m scripts.notify_preorder --sample                      # sample pre-order PD-MAU-THONGBAO
    python -m scripts.notify_preorder --sample --payment UNPAID     # mẫu 1 (chưa thanh toán)
    python -m scripts.notify_preorder --sample --payment PAID       # mẫu 2 (đã thanh toán)
    python -m scripts.notify_preorder --sample --event PREORDER_CREATED
    python -m scripts.notify_preorder --preorder-id 42 --event PREORDER_READY

--sample creates (once) a READY pre-order at CN01 whose phone / email are SMS_TEST_TO / EMAIL_TEST_TO
from .env (the team's phone and mailbox), so the real SMS / email reach the team. It is kept so the
rows of every run stay attached to it. Requires seed_auth and the SMTP / eSMS settings in .env.
"""
import argparse
import asyncio
import json
import sys

from sqlalchemy import text

from app.core.config import settings
from app.core.mailer import mask_email
from app.core.sms import mask_phone
from app.db.session import close_engine, standalone_transaction
from app.modules.notifications.service import notify_preorder
from app.modules.notifications.templates import EVENT_TYPES

SAMPLE_CODE = "PD-MAU-THONGBAO"
SAMPLE_ITEMS = [  # sku, product name snapshot, unit price, quantity (needs scripts.seed_catalog)
    ("SP-MAU-02-XANH-M", "Áo sơ mi mẫu - Xanh M", 250000, 2),
    ("SP-MAU-03-M", "Quần kaki mẫu - Đen M", 300000, 1),
]


async def sample_preorder(payment: str | None = None) -> int:
    if not settings.SMS_TEST_TO and not settings.EMAIL_TEST_TO:
        raise SystemExit("Đặt SMS_TEST_TO và/hoặc EMAIL_TEST_TO trong .env trước")
    async with standalone_transaction() as db:
        branch = (await db.execute(text("SELECT branch_id FROM branches WHERE branch_code = 'CN01'"))).scalar()
        if branch is None:
            raise SystemExit("Chạy python -m scripts.seed_auth trước")
        await db.execute(
            text(
                """INSERT INTO preorders (preorder_code, branch_id, customer_name, customer_phone, customer_email,
                   total_amount, payment_status, status, ready_at)
                   VALUES (:c, :b, 'Trần Thị Mai', :p, :e, 250000, 'PAID', 'READY', UTC_TIMESTAMP())
                   ON DUPLICATE KEY UPDATE customer_name = VALUES(customer_name), customer_phone = VALUES(customer_phone), customer_email = VALUES(customer_email)"""
            ),
            {"c": SAMPLE_CODE, "b": branch, "p": settings.SMS_TEST_TO or None, "e": settings.EMAIL_TEST_TO or None},
        )
        preorder_id = (await db.execute(text("SELECT preorder_id FROM preorders WHERE preorder_code = :c"), {"c": SAMPLE_CODE})).scalar_one()
        # Snapshot lines (2 products) once, and a hold deadline like the pre-order module sets it (UTC)
        if not (await db.execute(text("SELECT 1 FROM preorder_items WHERE preorder_id = :p LIMIT 1"), {"p": preorder_id})).first():
            for sku, name, price, qty in SAMPLE_ITEMS:
                variant = (await db.execute(text("SELECT variant_id FROM product_variants WHERE sku = :s"), {"s": sku})).scalar()
                if variant is None:
                    raise SystemExit("Chạy python -m scripts.seed_catalog trước")
                await db.execute(
                    text("""INSERT INTO preorder_items (preorder_id, variant_id, product_name_snapshot, sku_snapshot, unit_price,
                            quantity, allocated_quantity, line_total) VALUES (:p, :v, :n, :s, :u, :q, :q, :t)"""),
                    {"p": preorder_id, "v": variant, "n": name, "s": sku, "u": price, "q": qty, "t": price * qty},
                )
        await db.execute(
            text("""UPDATE preorders SET total_amount = (SELECT SUM(line_total) FROM preorder_items WHERE preorder_id = :p),
                    ready_at = UTC_TIMESTAMP(), expires_at = UTC_TIMESTAMP() + INTERVAL :d DAY WHERE preorder_id = :p"""),
            {"p": preorder_id, "d": settings.PREORDER_READY_DAYS},
        )
        if payment:
            await db.execute(text("UPDATE preorders SET payment_status = :s WHERE preorder_id = :p"), {"s": payment, "p": preorder_id})
        return preorder_id


async def main() -> int:
    parser = argparse.ArgumentParser(description="Send a real pre-order notification")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sample", action="store_true", help=f"use the sample pre-order {SAMPLE_CODE}")
    group.add_argument("--preorder-id", type=int)
    parser.add_argument("--event", default="PREORDER_READY", choices=EVENT_TYPES)
    parser.add_argument("--payment", choices=["PAID", "UNPAID"], help="--sample only: set the payment status (mẫu 2 / mẫu 1)")
    args = parser.parse_args()

    preorder_id = await sample_preorder(args.payment) if args.sample else args.preorder_id
    print(f"notify_preorder({preorder_id}, {args.event!r}) ...")
    outcome = await notify_preorder(preorder_id, args.event)
    print(json.dumps(outcome.to_dict(), ensure_ascii=False, indent=2))

    if outcome.notification_ids:
        async with standalone_transaction() as db:
            rows = (
                await db.execute(
                    text(
                        f"""SELECT notification_id, channel, recipient, status, provider_message_id, error_message, sent_at, message
                            FROM notifications WHERE notification_id IN ({','.join(map(str, outcome.notification_ids))})
                            ORDER BY notification_id"""
                    )
                )
            ).mappings().all()
        print("\nBản ghi notifications:")
        for r in rows:
            who = mask_phone(r["recipient"]) if r["channel"] == "SMS" else mask_email(r["recipient"])
            print(f"  #{r['notification_id']} {r['channel']:<5} {who:<18} {r['status']:<7} sent_at={r['sent_at']} "
                  f"provider_id={r['provider_message_id']} error={r['error_message']}")
            print(f"      message: {r['message'].splitlines()[0][:110]}")
    await close_engine()
    return 0 if outcome.status == "SENT" else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(asyncio.run(main()))
