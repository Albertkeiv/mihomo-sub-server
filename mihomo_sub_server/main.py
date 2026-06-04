from __future__ import annotations

import fnmatch
import logging
import os
import threading
import time
from collections import defaultdict, deque

from fastapi import FastAPI, Request

logger = logging.getLogger(__name__)
from fastapi.responses import Response

from mihomo_sub_server.config import AppConfig, ConfigError, RateLimitConfig, load_config

DEFAULT_CONFIG_PATH = "/app/config.yaml"


class _RateLimiter:
    """Sliding-window in-memory rate limiter, keyed by client IP."""

    def __init__(self, cfg: RateLimitConfig) -> None:
        self._requests = cfg.requests
        self._window = cfg.window_seconds
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def is_allowed(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            dq = self._buckets[key]
            while dq and dq[0] < cutoff:
                dq.popleft()
            if len(dq) >= self._requests:
                return False
            dq.append(now)
            return True


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

        if allowed_uas:
            if not any(fnmatch.fnmatch(ua, pattern) for pattern in allowed_uas):
                return Response(status_code=404)

        if rate_limiter is not None:
            if not rate_limiter.is_allowed(client_ip):
                return Response(status_code=429)

        url_path = f"/{request_path}"
        subscription = app_config.subscriptions.get(url_path)
        if subscription is None:
            return Response(status_code=404)
        return Response(content=subscription.content, media_type="application/yaml")

    return app


__all__ = ["AppConfig", "ConfigError", "create_app"]
