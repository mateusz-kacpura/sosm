"""Password hashing and session management for SOSM."""

import logging
import secrets
import time

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

logger = logging.getLogger(__name__)

ph = PasswordHasher()

# In-memory session store (single-process standalone app)
_sessions: dict[str, float] = {}  # token -> expiry_timestamp

# Cached flag — set during startup, updated when password is set
_password_set: bool = False

SESSION_COOKIE = "sosm_session"
SESSION_MAX_AGE = 24 * 60 * 60  # 24 hours


def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def create_session() -> str:
    token = secrets.token_urlsafe(32)
    _sessions[token] = time.time() + SESSION_MAX_AGE
    return token


def validate_session(token: str) -> bool:
    expiry = _sessions.get(token)
    if expiry is None:
        return False
    if time.time() > expiry:
        _sessions.pop(token, None)
        return False
    return True


def invalidate_session(token: str):
    _sessions.pop(token, None)


def password_is_set() -> bool:
    return _password_set


def mark_password_set():
    global _password_set
    _password_set = True


async def init_password_check():
    """Check if a password exists in the database (called during startup)."""
    global _password_set
    try:
        from sqlalchemy import select
        from app.core.database import AsyncSessionLocal
        from app.models.models import AppAuth

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(AppAuth).limit(1))
            _password_set = result.scalar_one_or_none() is not None
        if _password_set:
            logger.info("Password protection enabled")
        else:
            logger.info("No password set — panel is open until password is configured")
    except Exception:
        _password_set = False
