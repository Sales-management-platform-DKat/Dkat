"""Run ONE pass of the notification retry job now (the app also runs it every 5 minutes).

Run from backend/:  python -m scripts.retry_notifications
Useful for testing, or from a scheduler (cron / Task Scheduler) when NOTIFY_RETRY_ENABLED=false.
"""
import asyncio
import json
import sys

from app.db.session import close_engine
from app.modules.notifications.retry import retry_failed_notifications


async def main() -> int:
    summary = await retry_failed_notifications()
    print(json.dumps(summary))
    await close_engine()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
