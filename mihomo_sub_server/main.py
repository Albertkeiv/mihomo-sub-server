from __future__ import annotations

import fnmatch
import logging
import os
import threading
import time
from collections import defaultdict, deque

from fastapi import FastAPI, Request

logger = logging.getLogger("uvicorn.error")
from fastapi.responses import Response

from mihomo_sub_server.config import AppConfig, ConfigError, RateLimitConfig, load_config

DEFAULT_CONFIG_PATH = "/app/config.yaml"


class _RateLimiter:
    """Sliding-window in-memory rate limiter, keyed by client IP.

    Only failed requests (wrong path / blocked UA) are counted.
    Successful requests are never charged.
    """

    def __init__(self, cfg: RateLimitConfig) -> None:
        self._requests = cfg.requests
        self._window = cfg.window_seconds
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def is_blocked(self, key: str) -> bool:
        """True if the key has exceeded its failure quota."""
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            dq = self._buckets[key]
            while dq and dq[0] < cutoff:
                dq.popleft()
            return len(dq) >= self._requests

    def record_failure(self, key: str) -> None:
        """Count one failed request for this key."""
        with self._lock:
            self._buckets[key].append(time.monotonic())


def create_app(config_path: str | None = None) -> FastAPI:
    app_config = load_config(config_path or os.getenv("APP_CONFIG", DEFAULT_CONFIG_PATH))
    app = FastAPI(title="Mihomo Subscription Server")

    rate_limiter = (
        _RateLimiter(app_config.server.rate_limit)
        if app_config.server.rate_limit is not None
        else None
    )
    allowed_uas = app_config.server.allowed_user_agents

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/{request_path:path}")
    def get_subscription(request_path: str, request: Request) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        ua = request.headers.get("user-agent", "")
        logger.info("request ip=%s path=/%s ua=%r", client_ip, request_path, ua)

        if rate_limiter is not None and rate_limiter.is_blocked(client_ip):
            return Response(status_code=429)

        if allowed_uas and not any(fnmatch.fnmatch(ua, pattern) for pattern in allowed_uas):
            if rate_limiter is not None:
                rate_limiter.record_failure(client_ip)
            return Response(status_code=404)

        url_path = f"/{request_path}"
        subscription = app_config.subscriptions.get(url_path)
        if subscription is None:
            if rate_limiter is not None:
                rate_limiter.record_failure(client_ip)
            return Response(status_code=404)

        return Response(content=subscription.content, media_type="application/yaml")

    return app


__all__ = ["AppConfig", "ConfigError", "create_app"]
