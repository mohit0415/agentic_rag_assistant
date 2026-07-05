import asyncio
import json
import re
import threading
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Deque, Dict, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

import httpx

from ..config.config import logger


_RETRY_DELAY_RE = re.compile(r'retryDelay["\']?\s*:\s*["\']?(\d+(?:\.\d+)?)s')


_MAX_RETRY_SLEEP = 70.0

_PACIFIC = ZoneInfo("America/Los_Angeles")


def _seconds_until_pt_reset() -> float:
    now = datetime.now(_PACIFIC)
    reset = (now + timedelta(days=1)).replace(
        hour=0, minute=5, second=0, microsecond=0
    )
    return (reset - now).total_seconds()


def _pt_reset_human() -> str:
    hours = _seconds_until_pt_reset() / 3600.0
    return f"in about {hours:.1f} hours (midnight Pacific time)"


def _is_daily_quota(body_text: str) -> bool:
    return "PerDay" in body_text


def _delay_for_429(headers: httpx.Headers, body_text: str, attempt: int) -> float:
    retry_after = headers.get("retry-after")
    if retry_after:
        try:
            return min(float(retry_after) + 1.0, _MAX_RETRY_SLEEP)
        except ValueError:
            pass
    if body_text:
        match = _RETRY_DELAY_RE.search(body_text)
        if match:
            return min(float(match.group(1)) + 1.0, _MAX_RETRY_SLEEP)
    return min(2.0 * (2 ** attempt), _MAX_RETRY_SLEEP)


class SlidingWindowLimiter:

    def __init__(self, max_requests: int, window_seconds: float = 60.0):
        self.max_requests = max(1, int(max_requests))
        self.window = float(window_seconds)
        self._lock = threading.Lock()
        self._slots: Deque[float] = deque()  # scheduled send times (monotonic)

    def reserve(self) -> float:
        with self._lock:
            now = time.monotonic()
            while self._slots and self._slots[0] <= now - self.window:
                self._slots.popleft()
            if len(self._slots) < self.max_requests:
                start = now
            else:
                start = max(now, self._slots[-self.max_requests] + self.window)
            self._slots.append(start)
            return max(0.0, start - now)


class _BucketRouter:


    def __init__(self, llm_limiter: SlidingWindowLimiter,
                 embed_limiter: SlidingWindowLimiter):
        self._llm = llm_limiter
        self._embed = embed_limiter

    def limiter_for(self, request: httpx.Request) -> SlidingWindowLimiter:
        return self._embed if "embeddings" in request.url.path else self._llm


class ModelFallback:

    def __init__(self, chain: Sequence[str]):
        self.chain: List[str] = [m.strip() for m in chain if m and m.strip()]
        self._dead: Dict[str, float] = {}  # model -> monotonic expiry
        self._lock = threading.Lock()

    def _alive_locked(self, model: str) -> bool:
        expiry = self._dead.get(model)
        if expiry is None:
            return True
        if time.monotonic() >= expiry:
            del self._dead[model]
            return True
        return False

    def pick(self, requested: str) -> Optional[str]:
        with self._lock:
            if self._alive_locked(requested):
                return requested
            for model in self.chain:
                if model != requested and self._alive_locked(model):
                    return model
            return None

    def kill(self, model: str, seconds: Optional[float] = None) -> None:
        with self._lock:
            self._dead[model] = time.monotonic() + (
                seconds if seconds is not None else _seconds_until_pt_reset()
            )


def _request_model(request: httpx.Request) -> Optional[str]:
    try:
        return json.loads(request.content).get("model")
    except Exception:
        return None


def _with_model(request: httpx.Request, model: str) -> httpx.Request:
    data = json.loads(request.content)
    data["model"] = model
    headers = [(k, v) for k, v in request.headers.items()
               if k.lower() != "content-length"]
    return httpx.Request(
        request.method, request.url, headers=headers,
        content=json.dumps(data).encode("utf-8"),
    )


def _all_exhausted_response(request: httpx.Request,
                            fallback: ModelFallback) -> httpx.Response:
    chain = ", ".join(fallback.chain) or "the configured models"
    message = (
        f"This Gemini API key's FREE daily quota is used up for ALL "
        f"available models ({chain}). It refills {_pt_reset_human()}. "
        f"To keep going right now: log in with a Gemini key from a "
        f"DIFFERENT Google project (each project has its own free quota), "
        f"or enable billing on this key's project."
    )
    logger.error("Gemini DAILY quota exhausted on every fallback model")
    return httpx.Response(
        status_code=429,
        json={"error": {"message": message, "type": "insufficient_quota",
                        "code": "daily_quota_exhausted"}},
        request=request,
    )


def _daily_quota_response(request: httpx.Request, what: str) -> httpx.Response:
    message = (
        f"This Gemini API key's FREE daily quota for {what} is used up. "
        f"It refills {_pt_reset_human()}. Use a key from a different Google "
        f"project or enable billing to continue today."
    )
    logger.error(f"Gemini DAILY quota exhausted for {what}")
    return httpx.Response(
        status_code=429,
        json={"error": {"message": message, "type": "insufficient_quota",
                        "code": "daily_quota_exhausted"}},
        request=request,
    )


class _RetryLogic:

    def __init__(self, fallback: ModelFallback, max_attempts: int):
        self.fallback = fallback
        self.max_attempts = max(1, int(max_attempts))

    def step(self, request: httpx.Request, response: httpx.Response,
             body_text: str, is_chat: bool, model: Optional[str],
             minute_retries: int):
        status = response.status_code

        if is_chat and model and status == 404:
            logger.warning(f"Gemini model {model} unavailable (404) — falling back")
            self.fallback.kill(model, seconds=6 * 3600)
            target = self.fallback.pick(model)
            if target is None:
                return ("return", _rebuild(response, body_text, request))
            return ("switch", _with_model(request, target))

        if status in (500, 503):
            if minute_retries < self.max_attempts - 1:
                delay = _delay_for_429(response.headers, body_text, minute_retries)
                logger.warning(
                    f"Gemini {status} overloaded (retry {minute_retries + 1}/"
                    f"{self.max_attempts}) — waiting {delay:.1f}s"
                )
                return ("retry_after", delay)
            if is_chat and model:
                logger.warning(
                    f"Gemini model {model} still {status} after "
                    f"{self.max_attempts} attempts — falling back to another model"
                )
                self.fallback.kill(model, seconds=120)
                target = self.fallback.pick(model)
                if target is None:
                    return ("return", _rebuild(response, body_text, request))
                logger.info(f"Gemini overload fallback: {model} -> {target}")
                return ("switch", _with_model(request, target))
            return ("return", _rebuild(response, body_text, request))

        if status != 429:
            return ("return", _rebuild(response, body_text, request))

        if _is_daily_quota(body_text):
            if is_chat and model:
                logger.warning(
                    f"Gemini model {model} DAILY pool exhausted — falling back"
                )
                self.fallback.kill(model)
                target = self.fallback.pick(model)
                if target is None:
                    return ("return", _all_exhausted_response(request, self.fallback))
                logger.info(f"Gemini fallback: {model} -> {target}")
                return ("switch", _with_model(request, target))
            return ("return", _daily_quota_response(request, "embeddings"))

        if minute_retries >= self.max_attempts - 1:
            return ("return", _rebuild(response, body_text, request))
        delay = _delay_for_429(response.headers, body_text, minute_retries)
        logger.warning(
            f"Gemini 429 (retry {minute_retries + 1}/{self.max_attempts}) — "
            f"waiting {delay:.1f}s"
        )
        return ("retry_after", delay)


def _rebuild(response: httpx.Response, body_text: str,
             request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        status_code=response.status_code,
        headers=response.headers,
        content=body_text.encode("utf-8"),
        request=request,
    )


class RateLimitedTransport(httpx.HTTPTransport):

    def __init__(self, router: _BucketRouter, fallback: ModelFallback,
                 max_attempts: int = 5, **kwargs):
        super().__init__(**kwargs)
        self._router = router
        self._logic = _RetryLogic(fallback, max_attempts)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        request.read()  
        limiter = self._router.limiter_for(request)
        is_chat = "chat/completions" in request.url.path
        model = _request_model(request) if is_chat else None

        if is_chat and model:
            target = self._logic.fallback.pick(model)
            if target is None:
                return _all_exhausted_response(request, self._logic.fallback)
            if target != model:
                logger.info(f"Gemini pre-send fallback: {model} -> {target}")
                request = _with_model(request, target)
                model = target

        minute_retries = 0
        while True:
            wait = limiter.reserve()
            if wait > 0:
                logger.info(f"Gemini pacing: waiting {wait:.1f}s before request")
                time.sleep(wait)
            response = super().handle_request(request)
            if response.status_code not in (429, 404, 500, 503):
                return response
            body_text = response.read().decode("utf-8", errors="ignore")
            response.close()
            action, payload = self._logic.step(
                request, response, body_text, is_chat, model, minute_retries
            )
            if action == "return":
                return payload
            if action == "switch":
                request = payload
                model = _request_model(request)
                continue
            minute_retries += 1
            time.sleep(payload) 


class AsyncRateLimitedTransport(httpx.AsyncHTTPTransport):

    def __init__(self, router: _BucketRouter, fallback: ModelFallback,
                 max_attempts: int = 5, **kwargs):
        super().__init__(**kwargs)
        self._router = router
        self._logic = _RetryLogic(fallback, max_attempts)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        await request.aread()
        limiter = self._router.limiter_for(request)
        is_chat = "chat/completions" in request.url.path
        model = _request_model(request) if is_chat else None

        if is_chat and model:
            target = self._logic.fallback.pick(model)
            if target is None:
                return _all_exhausted_response(request, self._logic.fallback)
            if target != model:
                logger.info(f"Gemini pre-send fallback: {model} -> {target}")
                request = _with_model(request, target)
                model = target

        minute_retries = 0
        while True:
            wait = limiter.reserve() 
            if wait > 0:
                logger.info(f"Gemini pacing: waiting {wait:.1f}s before request")
                await asyncio.sleep(wait)
            response = await super().handle_async_request(request)
            if response.status_code not in (429, 404, 500, 503):
                return response
            body_text = (await response.aread()).decode("utf-8", errors="ignore")
            await response.aclose()
            action, payload = self._logic.step(
                request, response, body_text, is_chat, model, minute_retries
            )
            if action == "return":
                return payload
            if action == "switch":
                request = payload
                model = _request_model(request)
                continue
            minute_retries += 1
            await asyncio.sleep(payload)  

_clients_lock = threading.Lock()
_client_pairs: Dict[str, Tuple[httpx.Client, httpx.AsyncClient]] = {}


def get_gemini_http_clients(
    api_key: str,
    llm_rpm: int,
    embed_rpm: int,
    max_attempts: int = 5,
    timeout_seconds: float = 120.0,
    fallback_models: Optional[Sequence[str]] = None,
) -> Tuple[httpx.Client, httpx.AsyncClient]:
    with _clients_lock:
        pair = _client_pairs.get(api_key)
        if pair is None:
            router = _BucketRouter(
                SlidingWindowLimiter(llm_rpm),
                SlidingWindowLimiter(embed_rpm),
            )
            fallback = ModelFallback(fallback_models or [])
            timeout = httpx.Timeout(timeout_seconds, connect=30.0)
            pair = (
                httpx.Client(
                    transport=RateLimitedTransport(router, fallback, max_attempts),
                    timeout=timeout,
                ),
                httpx.AsyncClient(
                    transport=AsyncRateLimitedTransport(router, fallback, max_attempts),
                    timeout=timeout,
                ),
            )
            if len(_client_pairs) > 32:
                for old_sync, _old_async in _client_pairs.values():
                    try:
                        old_sync.close()
                    except Exception:
                        pass
                _client_pairs.clear()
            _client_pairs[api_key] = pair
            logger.info(
                f"Gemini rate-limited clients built (llm={llm_rpm} RPM, "
                f"embed={embed_rpm} RPM, retries={max_attempts}, "
                f"fallback chain={list(fallback.chain)})"
            )
        return pair
