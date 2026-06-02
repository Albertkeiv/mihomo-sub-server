from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

from mihomo_sub_server.config import ConfigError, load_subscriptions

DEFAULT_CONFIG_PATH = "/app/config.yaml"


def create_app(config_path: str | None = None) -> FastAPI:
    subscriptions = load_subscriptions(config_path or os.getenv("APP_CONFIG", DEFAULT_CONFIG_PATH))
    app = FastAPI(title="Mihomo Subscription Server")
    app.state.subscriptions = subscriptions

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/{request_path:path}")
    def get_subscription(request_path: str) -> Response:
        url_path = f"/{request_path}"
        subscription = subscriptions.get(url_path)
        if subscription is None:
            raise HTTPException(status_code=404, detail="Subscription not found")
        return Response(content=subscription.content, media_type="application/yaml")

    return app


__all__ = ["ConfigError", "create_app"]

