"""Log each request: METHOD URL STATUS - duration ms.

Query values that may hold personal data (phone, email, search keyword) are replaced by *** so
the application log never stores them (NFR-08), e.g. /customers/quick-search?phone=***.
"""
import time
from urllib.parse import parse_qsl, urlencode

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.utils.logger import get_logger

logger = get_logger("app.request")

SENSITIVE_QUERY_KEYS = frozenset({"phone", "email", "keyword"})


def redact_query(qs: str) -> str:
    if not qs:
        return qs
    pairs = parse_qsl(qs, keep_blank_values=True)
    if not any(k.lower() in SENSITIVE_QUERY_KEYS for k, _ in pairs):
        return qs
    return urlencode([(k, "***" if k.lower() in SENSITIVE_QUERY_KEYS else v) for k, v in pairs], safe="*")


class RequestLoggerMiddleware:
    """Pure ASGI middleware (does not wrap the response body, so it is lighter than BaseHTTPMiddleware)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            ms = (time.perf_counter() - start) * 1000
            path = scope.get("path", "")
            qs = redact_query(scope.get("query_string", b"").decode("latin-1"))
            url = f"{path}?{qs}" if qs else path
            line = f"{scope['method']} {url} {status_code} - {ms:.1f} ms"
            if status_code >= 500:
                logger.error(line)
            elif status_code >= 400:
                logger.warning(line)
            else:
                logger.info(line)
