import os

from dotenv import load_dotenv
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

load_dotenv()

RATE_LIMIT_QUERY: str = os.getenv("RATE_LIMIT_QUERY", "10/minute")
RATE_LIMIT_UPLOAD: str = os.getenv("RATE_LIMIT_UPLOAD", "5/minute")


SESSION_HEADER = "X-Session-Id"


def session_key_func(request: Request) -> str:
    session_id = request.headers.get(SESSION_HEADER)
    if session_id:
        return f"session:{session_id}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=session_key_func, headers_enabled=True)
