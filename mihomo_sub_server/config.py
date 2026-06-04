from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Raised when the application configuration is invalid."""


_SERVER_KEYS = {"rate_limit", "allowed_user_agents"}
_RESERVED_PATHS = {"/healthz", "/docs", "/redoc", "/openapi.json"}


@dataclass(frozen=True)
class RateLimitConfig:
    requests: int
    window_seconds: int


@dataclass(frozen=True)
class ServerConfig:
    rate_limit: RateLimitConfig | None
    allowed_user_agents: tuple[str, ...]


@dataclass(frozen=True)
class Subscription:
    user: str
    url_prefix: str
    config_path: Path
    content: str


@dataclass(frozen=True)
class AppConfig:
    server: ServerConfig
    subscriptions: dict[str, Subscription]


def load_config(config_path: str | Path) -> AppConfig:
    path = Path(config_path)
    if not path.exists():
        raise ConfigError(f"Config file does not exist: {path}")
    if not path.is_file():
        raise ConfigError(f"Config path is not a file: {path}")

    raw_config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw_config is None:
        raise ConfigError("Config file is empty")
    if not isinstance(raw_config, dict):
        raise ConfigError("Config root must be a mapping of users")

    server_config = _parse_server_config(raw_config)

    subscriptions: dict[str, Subscription] = {}
    for user, value in raw_config.items():
        if user in _SERVER_KEYS:
            continue
        if not isinstance(user, str) or not user:
            raise ConfigError("User names must be non-empty strings")
        if not isinstance(value, dict):
            raise ConfigError(f"User '{user}' must be a mapping")

        unknown_keys = set(value) - {"url_prefix", "config"}
        if unknown_keys:
            keys = ", ".join(sorted(str(key) for key in unknown_keys))
            raise ConfigError(f"User '{user}' has unknown keys: {keys}")

        url_prefix = value.get("url_prefix")
        if not isinstance(url_prefix, str) or not url_prefix:
            raise ConfigError(f"User '{user}' must define a non-empty url_prefix")
        if not url_prefix.startswith("/"):
            raise ConfigError(f"User '{user}' url_prefix must start with '/'")
        if url_prefix in _RESERVED_PATHS:
            raise ConfigError(f"url_prefix '{url_prefix}' is reserved")
        if url_prefix in subscriptions:
            other_user = subscriptions[url_prefix].user
            raise ConfigError(
                f"Duplicate url_prefix '{url_prefix}' for users '{other_user}' and '{user}'"
            )

        user_config_path = _resolve_config_path(path, value.get("config"), user)
        content = user_config_path.read_text(encoding="utf-8")
        subscriptions[url_prefix] = Subscription(
            user=user,
            url_prefix=url_prefix,
            config_path=user_config_path,
            content=content,
        )

    return AppConfig(server=server_config, subscriptions=subscriptions)


def _parse_server_config(raw_config: dict[str, Any]) -> ServerConfig:
    rate_limit = _parse_rate_limit(raw_config.get("rate_limit"))

    ua_raw = raw_config.get("allowed_user_agents")
    if ua_raw is None:
        allowed_user_agents: tuple[str, ...] = ()
    elif isinstance(ua_raw, list):
        for i, item in enumerate(ua_raw):
            if not isinstance(item, str) or not item:
                raise ConfigError(f"allowed_user_agents[{i}] must be a non-empty string")
        allowed_user_agents = tuple(ua_raw)
    else:
        raise ConfigError("allowed_user_agents must be a list of strings")

    return ServerConfig(rate_limit=rate_limit, allowed_user_agents=allowed_user_agents)


def _parse_rate_limit(value: Any) -> RateLimitConfig | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ConfigError("rate_limit must be a mapping")

    unknown_keys = set(value) - {"requests", "window_seconds"}
    if unknown_keys:
        keys = ", ".join(sorted(str(k) for k in unknown_keys))
        raise ConfigError(f"rate_limit has unknown keys: {keys}")

    requests = value.get("requests")
    if not isinstance(requests, int) or requests <= 0:
        raise ConfigError("rate_limit.requests must be a positive integer")

    window_seconds = value.get("window_seconds")
    if not isinstance(window_seconds, int) or window_seconds <= 0:
        raise ConfigError("rate_limit.window_seconds must be a positive integer")

    return RateLimitConfig(requests=requests, window_seconds=window_seconds)


def _resolve_config_path(app_config_path: Path, value: Any, user: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ConfigError(f"User '{user}' must define a non-empty config")

    config_path = Path(value)
    if not config_path.is_absolute():
        config_path = app_config_path.parent / config_path
    if not config_path.exists():
        raise ConfigError(f"User '{user}' config file does not exist: {config_path}")
    if not config_path.is_file():
        raise ConfigError(f"User '{user}' config path is not a file: {config_path}")
    return config_path
