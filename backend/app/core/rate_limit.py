"""In-memory sliding-window rate limit per client IP (one process; each uvicorn worker counts on its own).

    limiter = SlidingWindowLimiter(limit=60, window_seconds=60)
    router = APIRouter(dependencies=[Depends(rate_limit(limiter))])

Over the limit: 429 {"code": "RATE_LIMIT_EXCEEDED", ...} with Retry-After. Every answer carries
X-RateLimit-Limit / X-RateLimit-Remaining. The client IP is request.client.host (uvicorn resolves
X-Forwarded-For only from trusted proxies, --forwarded-allow-ips).
"""
import math
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, Response


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: float = 60.0):
        self.limit, self.window = limit, window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str) -> tuple[bool, int, int]:
        """Record one request. Returns (allowed, remaining, retry_after_seconds)."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return False, 0, max(1, math.ceil(hits[0] + self.window - now))
            hits.append(now)
            if len(self._hits) > 10_000:  # forget idle clients so memory stays bounded
                for k in [k for k, v in self._hits.items() if not v or v[-1] <= now - self.window]:
                    del self._hits[k]
            return True, self.limit - len(hits), 0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def rate_limit(limiter: SlidingWindowLimiter):
    def dependency(request: Request, response: Response) -> None:
        ip = request.client.host if request.client else "unknown"
        allowed, remaining, retry_after = limiter.hit(ip)
        if not allowed:
            raise HTTPException(429, {"code": "RATE_LIMIT_EXCEEDED", "message": "Quá nhiều yêu cầu, vui lòng thử lại sau"},
                                headers={"Retry-After": str(retry_after), "X-RateLimit-Limit": str(limiter.limit),
                                         "X-RateLimit-Remaining": "0"})
        response.headers["X-RateLimit-Limit"] = str(limiter.limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

    return dependency
