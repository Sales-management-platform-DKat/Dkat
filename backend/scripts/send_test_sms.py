"""Send a real test SMS through eSMS.vn with the settings from .env (FR-09.1).

Run from backend/:
    python -m scripts.send_test_sms                    # to SMS_TEST_TO from .env, eSMS test template
    python -m scripts.send_test_sms --to 0912345678
    python -m scripts.send_test_sms --balance          # only show the eSMS balance
    python -m scripts.send_test_sms --sandbox          # eSMS validates, sends/charges nothing
    python -m scripts.send_test_sms --wrong-key        # wrong SecretKey on purpose: must print
                                                       # success=false (AUTH_FAILED), never crash
Prints {success, providerMessageId, error}. Exit code 0 when the result is the expected one.

Trial accounts can only send eSMS's registered test template with brandname "Baotrixemay":
    "<CODE> la ma xac minh dang ky Baotrixemay cua ban"   (CODE: up to 8 letters/digits)
so the default content is that template with a random 6-digit code (also avoids eSMS's
"same phone + same content once per 5 minutes" rule). Use --content once your own brandname and
template are registered.
"""
import argparse
import asyncio
import json
import secrets
import sys

from app.core.config import settings
from app.core.sms import get_balance, mask_phone, send_sms

TEST_TEMPLATE = "{code} la ma xac minh dang ky Baotrixemay cua ban"


async def main() -> int:
    parser = argparse.ArgumentParser(description="Send a DKat test SMS via eSMS.vn")
    parser.add_argument("--to", default=settings.SMS_TEST_TO, help="recipient (default: SMS_TEST_TO in .env)")
    parser.add_argument("--content", help="custom content (needs a registered brandname/template)")
    parser.add_argument("--sandbox", action="store_true", help="eSMS Sandbox=1: validate only, nothing sent")
    parser.add_argument("--wrong-key", action="store_true", help="use a wrong SecretKey on purpose")
    parser.add_argument("--balance", action="store_true", help="only print the account balance")
    args = parser.parse_args()

    if args.wrong_key:
        settings.ESMS_SECRET_KEY = "wrong-secret-key-on-purpose"  # this process only, .env untouched
    if args.sandbox:
        settings.ESMS_SANDBOX = True

    balance = await get_balance()
    print("Số dư eSMS:", json.dumps(balance, ensure_ascii=False))
    if args.balance:
        return 0 if balance["success"] else 1
    if not args.to:
        print("Thiếu người nhận: đặt SMS_TEST_TO trong .env hoặc truyền --to")
        return 2

    content = args.content or TEST_TEMPLATE.format(code=f"{secrets.randbelow(10**6):06d}")
    print(
        f"eSMS brandname={settings.ESMS_BRANDNAME} type={settings.ESMS_SMS_TYPE} "
        f"sandbox={settings.ESMS_SANDBOX} -> {mask_phone(args.to)}"
    )
    print(f"Nội dung: {content}")
    result = await send_sms(to=args.to, content=content)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    if result.success:
        print("Lưu ý: eSMS 100 = đã nhận yêu cầu; kiểm tra điện thoại để chắc tin đã tới.")
    expected = not result.success if args.wrong_key else result.success
    print("=> ĐÚNG như mong đợi" if expected else "=> KHÔNG như mong đợi")
    return 0 if expected else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(asyncio.run(main()))
