"""
JWT authentication — security core.

Flow (matches the design discussed):
  1. User POSTs username/password to /api/login.
  2. `authenticate_user` compares them (constant-time) against AUTH_USERNAME /
     AUTH_PASSWORD from the environment — no DB required.
  3. On success `create_access_token` signs a JWT whose payload carries
     {"sub": <username>, "exp": <now + JWT_EXPIRY_MINUTES>} with JWT_SECRET_KEY.
  4. The frontend stores the token and sends it as `Authorization: Bearer <token>`.
  5. `get_current_user` is attached as a dependency to every protected route, so
     the signature + expiry are verified BEFORE any embedding / LLM / RAG work
     runs. An attacker without a valid token never reaches the expensive pipeline.

The expiry duration is fully dynamic: set JWT_EXPIRY_MINUTES in the environment
and the value is interpreted in minutes everywhere in the code.
"""

from __future__ import annotations

import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt  # PyJWT
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..config.config import logger

load_dotenv()


class AuthSettings:
    """All auth-related configuration, loaded once from environment variables."""

    def __init__(self) -> None:
        # Secret used to sign/verify tokens. MUST be overridden in production.
        self.secret_key: str = os.getenv(
            "JWT_SECRET_KEY",
            "change-me-in-production-please-use-a-long-random-secret",
        )
        self.algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")

        # Expiry is read in MINUTES and used as minutes throughout the code.
        try:
            self.expiry_minutes: int = int(os.getenv("JWT_EXPIRY_MINUTES", "30"))
        except ValueError:
            logger.warning("JWT_EXPIRY_MINUTES is not a valid int; defaulting to 30")
            self.expiry_minutes = 30
        if self.expiry_minutes < 1:
            logger.warning("JWT_EXPIRY_MINUTES < 1; clamping to 1 minute")
            self.expiry_minutes = 1

        # Static credentials (no DB). Override these in .env.
        self.username: str = os.getenv("AUTH_USERNAME", "admin")
        self.password: str = os.getenv("AUTH_PASSWORD", "admin123")

        if self.secret_key.startswith("change-me"):
            logger.warning(
                "JWT_SECRET_KEY is using the insecure default — set JWT_SECRET_KEY in .env"
            )

    @property
    def expires_delta(self) -> timedelta:
        return timedelta(minutes=self.expiry_minutes)


# Single shared instance.
auth_settings = AuthSettings()

# HTTPBearer drives the Swagger "Authorize" button and pulls the token out of the
# `Authorization: Bearer <token>` header. auto_error=False lets us return a clean
# 401 with our own message instead of the default.
_bearer_scheme = HTTPBearer(auto_error=False)


def authenticate_user(username: str, password: str) -> bool:
    """Constant-time comparison of submitted credentials against env values."""
    user_ok = hmac.compare_digest(username or "", auth_settings.username)
    pass_ok = hmac.compare_digest(password or "", auth_settings.password)
    return user_ok and pass_ok


def create_access_token(
    subject: str,
    extra_claims: Optional[Dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Sign and return a JWT for `subject`, expiring after JWT_EXPIRY_MINUTES."""
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or auth_settings.expires_delta)

    payload: Dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": expire,
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, auth_settings.secret_key, algorithm=auth_settings.algorithm)


def decode_access_token(token: str) -> Dict[str, Any]:
    """Verify signature + expiry and return the decoded payload, or raise 401."""
    try:
        return jwt.decode(
            token,
            auth_settings.secret_key,
            algorithms=[auth_settings.algorithm],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> str:
    """FastAPI dependency: validate the Bearer token, return the username.

    Attached to protected routes so the check happens BEFORE any RAG work runs.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Provide a Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return username


async def get_current_claims(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> Dict[str, Any]:
    """FastAPI dependency: validate the Bearer token and return its FULL payload.

    Same gatekeeping as `get_current_user`, but returns the whole decoded payload
    so downstream code can read the per-user provider keys that were baked into
    the token at login (e.g. `llamaparse_api_key`). These are
    therefore only ever read AFTER the JWT signature + expiry have been verified.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Provide a Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    if not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload
