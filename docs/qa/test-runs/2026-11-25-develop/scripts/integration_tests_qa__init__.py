"""QA copy of integration_tests adapted to the current API contract (all routers under /api/v1).

Any request path that does not start with /api/ or /health gets the /api/v1 prefix. Test logic is unchanged.
"""
from fastapi.testclient import TestClient as _TestClient

_original_request = _TestClient.request


def _prefixed_request(self, method, url, *args, **kwargs):
    if isinstance(url, str) and url.startswith("/") and not url.startswith(("/api/", "/health")):
        url = "/api/v1" + url
    return _original_request(self, method, url, *args, **kwargs)


_TestClient.request = _prefixed_request
