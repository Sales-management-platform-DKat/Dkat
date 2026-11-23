"""Send a real test email with the SMTP settings from .env (FR-09.2).

Run from backend/:
    python -m scripts.send_test_email                       # to EMAIL_TEST_TO from .env
    python -m scripts.send_test_email --to team@example.com
    python -m scripts.send_test_email --wrong-password      # same settings, wrong password on purpose:
                                                            # must print success=false, never crash
Prints {success, providerMessageId, error}. Exit code 0 when the result is the expected one.

Gmail setup (.env): SMTP_HOST=smtp.gmail.com, SMTP_PORT=587, SMTP_SECURITY=starttls,
SMTP_USERNAME / SMTP_FROM_EMAIL = the Gmail address, SMTP_PASSWORD = an App Password
(Google account > Security > 2-Step Verification > App passwords), not the account password.
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone

from app.core.config import settings
from app.core.mailer import mask_email, send_email


async def main() -> int:
    parser = argparse.ArgumentParser(description="Send a DKat test email")
    parser.add_argument("--to", default=settings.EMAIL_TEST_TO, help="recipient (default: EMAIL_TEST_TO in .env)")
    parser.add_argument("--wrong-password", action="store_true", help="use a wrong SMTP password on purpose")
    args = parser.parse_args()
    if not args.to:
        print("Thiếu người nhận: đặt EMAIL_TEST_TO trong .env hoặc truyền --to")
        return 2

    if args.wrong_password:
        settings.SMTP_PASSWORD = "wrong-password-on-purpose"  # this process only, .env is untouched

    sent_at = datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M:%S")
    print(f"SMTP {settings.SMTP_HOST}:{settings.SMTP_PORT} ({settings.SMTP_SECURITY}) -> {mask_email(args.to)}")
    result = await send_email(
        to=args.to,
        subject=f"[DKat] Email thử nghiệm {sent_at}",
        body=(
            "Xin chào,\n\n"
            "Đây là email thử nghiệm từ backend DKat (FR-09.2: thông báo đặt trước).\n"
            f"Gửi lúc: {sent_at}\n\n"
            "Nếu bạn nhận được email này, cấu hình SMTP trong .env đã đúng.\n\n"
            "-- DKat"
        ),
        html=(
            "<p>Xin chào,</p><p>Đây là email thử nghiệm từ backend <b>DKat</b> "
            f"(FR-09.2: thông báo đặt trước).</p><p>Gửi lúc: {sent_at}</p>"
            "<p>Nếu bạn nhận được email này, cấu hình SMTP trong <code>.env</code> đã đúng.</p><p>-- DKat</p>"
        ),
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    expected = not result.success if args.wrong_password else result.success
    print("=> ĐÚNG như mong đợi" if expected else "=> KHÔNG như mong đợi")
    return 0 if expected else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(asyncio.run(main()))
