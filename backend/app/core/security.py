import base64
import hashlib
import hmac
import json
import secrets
import time

from app.core import config


_PASSWORD_ITERATIONS = 310_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _PASSWORD_ITERATIONS
    )
    return "pbkdf2_sha256${}${}${}".format(
        _PASSWORD_ITERATIONS,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            base64.urlsafe_b64decode(salt.encode("ascii")),
            int(iterations),
        )
        return hmac.compare_digest(
            actual, base64.urlsafe_b64decode(expected.encode("ascii"))
        )
    except (ValueError, TypeError):
        return False


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _auth_secret() -> bytes:
    secret = config.AUTH_SECRET_KEY.encode("utf-8")
    if len(secret) < 32:
        raise RuntimeError("DKAT_AUTH_SECRET_KEY must contain at least 32 characters.")
    return secret


def create_access_token(user_id: int, session_id: str, *, now: int | None = None) -> tuple[str, int]:
    issued_at = int(time.time()) if now is None else now
    expires_at = issued_at + config.ACCESS_TOKEN_TTL_SECONDS
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user_id),
        "sid": session_id,
        "iat": issued_at,
        "exp": expires_at,
        "type": "access",
        "jti": secrets.token_urlsafe(16),
    }
    signing_input = f"{_b64url(json.dumps(header, separators=(',', ':')).encode())}.{_b64url(json.dumps(payload, separators=(',', ':')).encode())}"
    signature = hmac.new(_auth_secret(), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url(signature)}", expires_at


def decode_access_token(token: str, *, now: int | None = None) -> dict | None:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        signing_input = f"{encoded_header}.{encoded_payload}"
        expected = hmac.new(_auth_secret(), signing_input.encode("ascii"), hashlib.sha256).digest()
        signature = base64.urlsafe_b64decode(encoded_signature + "=" * (-len(encoded_signature) % 4))
        if not hmac.compare_digest(expected, signature):
            return None
        header = json.loads(base64.urlsafe_b64decode(encoded_header + "=" * (-len(encoded_header) % 4)))
        payload = json.loads(base64.urlsafe_b64decode(encoded_payload + "=" * (-len(encoded_payload) % 4)))
        current_time = int(time.time()) if now is None else now
        if header != {"alg": "HS256", "typ": "JWT"}:
            return None
        if payload.get("type") != "access" or int(payload.get("exp", 0)) <= current_time:
            return None
        if int(payload.get("iat", current_time + 1)) > current_time:
            return None
        int(payload["sub"])
        if not isinstance(payload.get("sid"), str) or not payload["sid"]:
            return None
        return payload
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def create_refresh_token(remember_me: bool = False) -> tuple[str, str]:
    # The final bit is covered by the database hash, so it cannot be changed
    # to turn a session cookie into a persistent cookie (or the reverse).
    token = f"{secrets.token_urlsafe(48)}.{int(remember_me)}"
    return token, hash_access_token(token)


def refresh_token_is_persistent(token: str) -> bool:
    return token.rsplit(".", 1)[-1:] == ["1"]


def hash_access_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
