from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Raised when the application configuration is invalid."""


@dataclass(frozen=True)
class Subscription:
    user: str
    url_prefix: str
    config_path: Path
    content: str


def load_subscriptions(config_path: str | Path) -> dict[str, Subscription]:
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

    subscriptions: dict[str, Subscription] = {}
    for user, value in raw_config.items():
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
        _RESERVED = {"/healthz", "/docs", "/redoc", "/openapi.json"}
        if url_prefix in _RESERVED:
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

    return subscriptions


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

