"""
auth.py — server-side login for the dashboard.

Accounts come from the DASHBOARD_USERS environment variable, never from code:

    DASHBOARD_USERS=alice:pbkdf2_sha256.390000.<salt>.<hash>,bob:pbkdf2_sha256....

Generate a hash with `python backend/hash_password.py`. Sessions are HMAC-signed
tokens (SESSION_SECRET) kept in an HttpOnly cookie. Changing a user's password
changes their hash, which invalidates that user's existing sessions.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from collections import deque
from threading import Lock
from typing import Dict, Optional

COOKIE_NAME = "cimb_session"
SESSION_SECONDS = 12 * 60 * 60
PBKDF2_ITERATIONS = 390_000
LOGIN_FAILURE_LIMIT = 10          # per username...
LOGIN_FAILURE_WINDOW = 15 * 60    # ...within 15 minutes, then locked until older failures expire
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._@-]{1,64}$")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str, iterations: int = PBKDF2_ITERATIONS) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    # '.'-separated base64url: safe inside a docker compose env file (no '$', ':' or ',').
    return f"pbkdf2_sha256.{iterations}.{_b64(salt)}.{_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iterations, salt, digest = stored.split(".")
        if scheme != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), _unb64(salt), int(iterations))
        return hmac.compare_digest(candidate, _unb64(digest))
    except (ValueError, TypeError):
        return False


# Used for unknown usernames so a login takes the same time either way.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16), iterations=PBKDF2_ITERATIONS)


def load_users(raw: Optional[str] = None) -> Dict[str, str]:
    raw = os.getenv("DASHBOARD_USERS", "") if raw is None else raw
    users = {}
    for entry in raw.split(","):
        username, _, stored = entry.strip().partition(":")
        if USERNAME_PATTERN.match(username) and stored.startswith("pbkdf2_sha256."):
            users[username.lower()] = stored
    return users


def session_secret() -> bytes:
    secret = os.getenv("SESSION_SECRET", "").strip()
    return secret.encode() if len(secret) >= 32 else b""


def is_configured() -> bool:
    return bool(load_users()) and bool(session_secret())


def _password_version(stored: str) -> str:
    return hashlib.sha256(stored.encode()).hexdigest()[:12]


def authenticate(username: str, password: str) -> Optional[str]:
    """Return the canonical username when the password is correct."""
    key = (username or "").strip().lower()
    stored = load_users().get(key)
    if not verify_password(password or "", stored or _DUMMY_HASH) or not stored:
        return None
    return key


def create_session(username: str, now: Optional[float] = None) -> str:
    stored = load_users()[username]
    payload = {"u": username, "exp": int((now or time.time()) + SESSION_SECONDS), "v": _password_version(stored)}
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    signature = _b64(hmac.new(session_secret(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{signature}"


def read_session(token: Optional[str], now: Optional[float] = None) -> Optional[str]:
    """Return the username for a valid, unexpired token whose password is unchanged."""
    secret = session_secret()
    if not token or not secret or token.count(".") != 1:
        return None
    body, signature = token.split(".")
    expected = _b64(hmac.new(secret, body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        payload = json.loads(_unb64(body))
    except (ValueError, TypeError):
        return None
    stored = load_users().get(payload.get("u", ""))
    if not stored or payload.get("v") != _password_version(stored) or payload.get("exp", 0) < (now or time.time()):
        return None
    return payload["u"]


class LoginThrottle:
    """Counts failed logins per username so a password cannot be guessed quickly."""

    def __init__(self, limit: int = LOGIN_FAILURE_LIMIT, window: int = LOGIN_FAILURE_WINDOW):
        self.limit, self.window = limit, window
        self._failures: Dict[str, deque] = {}
        self._lock = Lock()

    def _recent(self, key: str, now: float) -> deque:
        bucket = self._failures.setdefault(key, deque())
        while bucket and now - bucket[0] >= self.window:
            bucket.popleft()
        return bucket

    def retry_after(self, username: str, now: Optional[float] = None) -> int:
        """Seconds until the next attempt is allowed; 0 when not locked."""
        now = time.monotonic() if now is None else now
        with self._lock:
            bucket = self._recent(username.strip().lower(), now)
            return max(1, int(self.window - (now - bucket[0]))) if len(bucket) >= self.limit else 0

    def failed(self, username: str, now: Optional[float] = None):
        now = time.monotonic() if now is None else now
        with self._lock:
            self._recent(username.strip().lower(), now).append(now)

    def succeeded(self, username: str):
        with self._lock:
            self._failures.pop(username.strip().lower(), None)
