import time
from collections import deque

from fastapi import Request

from app.config import settings
from app.errors import app_error

# ponytail: in-memory sliding window, single-process only; swap to Redis if running multiple workers
_calls: dict[str, deque] = {}


def rate_limited(scope: str):
    def dep(request: Request) -> None:
        limit = getattr(settings, f"rate_limit_{scope}")
        window = settings.rate_limit_window_seconds
        host = request.client.host if request.client else "unknown"
        key = f"{scope}:{host}"
        now = time.monotonic()
        bucket = _calls.setdefault(key, deque())
        while bucket and bucket[0] <= now - window:
            bucket.popleft()
        if len(bucket) >= limit:
            raise app_error("RATE_LIMITED", "Too many requests, try again later")
        bucket.append(now)

    return dep


def clear_rate_limit_store() -> None:
    _calls.clear()
