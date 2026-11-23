"""Per-IP request limiting for public (unauthenticated) endpoints.

Usage:
    _limiter = SlidingWindowLimiter(limit=60, window_seconds=60)
    router = APIRouter(dependencies=[Depends(rate_limit(_limiter))])

Sliding window kept in process memory: cheap enough for read endpoints called on every page view.
Limits are per worker process; run behind one worker or put a shared limiter (proxy / Redis) in front
when scaling out. The client IP is the TCP peer address; X-Forwarded-For is NOT trusted because any
client could forge it to dodge the limit.
"""
import math
import time
from collections import deque

from fastapi import Request, Response

from app.core.exceptions import AppError


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: float = 60.0, *, clock=time.monotonic) -> None:
        if limit < 1 or window_seconds <= 0:
            raise ValueError("limit must be >= 1 and window_seconds > 0")
        self.limit = limit
        self.window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._calls = 0

    def hit(self, key: str) -> tuple[bool, int, int]:
        """Record one request for `key`. Returns (allowed, remaining, retry_after_seconds).

        No await inside: on the asyncio event loop this runs atomically, no lock needed.
        A rejected request is not recorded, so a client that keeps retrying is not blocked forever.
        """
        now = self._clock()
        cutoff = now - self.window
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= cutoff:
            hits.popleft()
        self._calls += 1
        if self._calls % 1000 == 0:
            self._prune(cutoff)
        if len(hits) >= self.limit:
            return False, 0, max(1, math.ceil(hits[0] + self.window - now))
        hits.append(now)
        return True, self.limit - len(hits), 0

    def _prune(self, cutoff: float) -> None:
        """Drop idle IPs so memory stays bounded by the number of recently active clients."""
        for key in [k for k, h in self._hits.items() if not h or h[-1] <= cutoff]:
            del self._hits[key]

    def reset(self) -> None:
        self._hits.clear()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def rate_limit(limiter: SlidingWindowLimiter):
    """FastAPI dependency: 429 RATE_LIMIT_EXCEEDED (+ Retry-After) when the IP is over the limit."""

    async def dependency(request: Request, response: Response) -> None:
        allowed, remaining, retry_after = limiter.hit(client_ip(request))
        if not allowed:
            raise AppError(
                429,
                "RATE_LIMIT_EXCEEDED",
                f"Quá nhiều yêu cầu. Vui lòng thử lại sau {retry_after} giây",
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limiter.limit),
                    "X-RateLimit-Remaining": "0",
                },
            )
        response.headers["X-RateLimit-Limit"] = str(limiter.limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

    return dependency
