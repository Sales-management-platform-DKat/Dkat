"""Small HTTP helper for the develop E2E run: logs every request/response (tokens masked)."""
import json
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8010"
API = BASE + "/api/v1"


class Http:
    def __init__(self, log_path: Path):
        self.client = httpx.Client(base_url=API, timeout=30)
        self.log = open(log_path, "a", encoding="utf-8")
        self.current_tc = "SEED"

    def call(self, method, path, token=None, json_body=None, headers=None, params=None, ip=None):
        h = dict(headers or {})
        if token:
            h["Authorization"] = f"Bearer {token}"
        if ip:
            h["X-Forwarded-For"] = ip
        t0 = time.perf_counter()
        r = self.client.request(method, path, json=json_body, headers=h, params=params)
        ms = (time.perf_counter() - t0) * 1000
        try:
            body = r.json()
        except ValueError:
            body = r.text[:500]
        shown = json.dumps(body, ensure_ascii=False)
        for key in ("access_token", "refresh_token"):
            if isinstance(body, dict) and key in body:
                shown = shown.replace(body[key], "***")
        req = json.dumps(json_body, ensure_ascii=False) if json_body is not None else ""
        if "password" in req:
            req = req.replace(json_body.get("password", json_body.get("owner_password", "")) or "§", "***")
        self.log.write(f"[{time.strftime('%H:%M:%S')}] {self.current_tc} {method} /api/v1{path}"
                       f"{'?' + str(httpx.QueryParams(params)) if params else ''} {req}\n"
                       f"    -> {r.status_code} ({ms:.0f} ms) {shown[:1500]}\n")
        self.log.flush()
        return r
