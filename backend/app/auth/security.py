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
    
    def __init__(self) -> None:
        self.secret_key: str = os.getenv(
            "JWT_SECRET_KEY",
            "change-me-in-production-please-use-a-long-random-secret",
        )
        self.algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")

        try:
            self.expiry_minutes: int = int(os.getenv("JWT_EXPIRY_MINUTES", "30"))
        except ValueError:
            logger.warning("JWT_EXPIRY_MINUTES is not a valid int; defaulting to 30")
            self.expiry_minutes = 30
        if self.expiry_minutes < 1:
            logger.warning("JWT_EXPIRY_MINUTES < 1; clamping to 1 minute")
            self.expiry_minutes = 1
        self.username: str = os.getenv("AUTH_USERNAME", "admin")
        self.password: str = os.getenv("AUTH_PASSWORD", "admin123")

        if self.secret_key.startswith("change-me"):
            logger.warning(
                "JWT_SECRET_KEY is using the insecure default — set JWT_SECRET_KEY in .env"
            )

    @property
    def expires_delta(self) -> timedelta:
        return timedelta(minutes=self.expiry_minutes)


auth_settings = AuthSettings()

_bearer_scheme = HTTPBearer(auto_error=False)


def authenticate_user(username: str, password: str) -> bool:
    user_ok = hmac.compare_digest(username or "", auth_settings.username)
    pass_ok = hmac.compare_digest(password or "", auth_settings.password)
    return user_ok and pass_ok


def create_access_token(
    subject: str,
    extra_claims: Optional[Dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
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
