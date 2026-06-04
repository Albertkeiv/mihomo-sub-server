from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mihomo_sub_server.config import ConfigError
from mihomo_sub_server.main import create_app


MIHOMO_CONFIG = """\
proxies:
  - name: demo
    type: socks5
    server: 127.0.0.1
    port: 1080
"""


def write_file(path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _make_app(tmp_path, extra_config: str = ""):
    subscription_file = tmp_path / "somebody.yaml"
    app_config = tmp_path / "config.yaml"
    write_file(subscription_file, MIHOMO_CONFIG)
    write_file(
        app_config,
        f"""\
somebody:
  url_prefix: "/secret_path/secret_key"
  config: "{subscription_file.as_posix()}"
{extra_config}
""",
    )
    return TestClient(create_app(str(app_config)))


def test_serves_subscription_yaml(tmp_path):
    client = _make_app(tmp_path)
    response = client.get("/secret_path/secret_key")
    assert response.status_code == 200
    assert response.text == MIHOMO_CONFIG


def test_unknown_path_returns_404(tmp_path):
    client = _make_app(tmp_path)
    response = client.get("/unknown")
    assert response.status_code == 404


def test_duplicate_url_prefix_fails_startup(tmp_path):
    first_file = tmp_path / "first.yaml"
    second_file = tmp_path / "second.yaml"
    app_config = tmp_path / "config.yaml"
    write_file(first_file, MIHOMO_CONFIG)
    write_file(second_file, MIHOMO_CONFIG)
    write_file(
        app_config,
        f"""\
first:
  url_prefix: "/same"
  config: "{first_file.as_posix()}"
second:
  url_prefix: "/same"
  config: "{second_file.as_posix()}"
""",
    )
    with pytest.raises(ConfigError, match="Duplicate url_prefix"):
        create_app(str(app_config))


def test_missing_subscription_file_fails_startup(tmp_path):
    app_config = tmp_path / "config.yaml"
    write_file(
        app_config,
        f"""\
somebody:
  url_prefix: "/secret_path/secret_key"
  config: "{(tmp_path / 'missing.yaml').as_posix()}"
""",
    )
    with pytest.raises(ConfigError, match="does not exist"):
        create_app(str(app_config))


def test_subscription_content_type_is_application_yaml(tmp_path):
    client = _make_app(tmp_path)
    response = client.get("/secret_path/secret_key")
    assert response.headers["content-type"] == "application/yaml"


# --- User-Agent filtering ---

def test_allowed_user_agent_passes(tmp_path):
    client = _make_app(tmp_path, extra_config="""\
allowed_user_agents:
  - "clash*"
  - "mihomo*"
""")
    response = client.get("/secret_path/secret_key", headers={"user-agent": "clash/1.0"})
    assert response.status_code == 200


def test_forbidden_user_agent_returns_403(tmp_path):
    client = _make_app(tmp_path, extra_config="""\
allowed_user_agents:
  - "clash*"
""")
    response = client.get("/secret_path/secret_key", headers={"user-agent": "curl/7.0"})
    assert response.status_code == 403


def test_no_user_agent_filter_allows_all(tmp_path):
    client = _make_app(tmp_path)
    response = client.get("/secret_path/secret_key", headers={"user-agent": "anything"})
    assert response.status_code == 200


def test_user_agent_wildcard_matches(tmp_path):
    client = _make_app(tmp_path, extra_config="""\
allowed_user_agents:
  - "ClashForWindows/*"
""")
    response = client.get(
        "/secret_path/secret_key",
        headers={"user-agent": "ClashForWindows/0.20.39"},
    )
    assert response.status_code == 200


# --- Rate limiting ---

def test_rate_limit_allows_within_limit(tmp_path):
    client = _make_app(tmp_path, extra_config="""\
rate_limit:
  requests: 3
  window_seconds: 60
""")
    for _ in range(3):
        assert client.get("/secret_path/secret_key").status_code == 200


def test_rate_limit_blocks_after_exceeded(tmp_path):
    client = _make_app(tmp_path, extra_config="""\
rate_limit:
  requests: 2
  window_seconds: 60
""")
    client.get("/secret_path/secret_key")
    client.get("/secret_path/secret_key")
    response = client.get("/secret_path/secret_key")
    assert response.status_code == 429


def test_healthz_not_rate_limited(tmp_path):
    client = _make_app(tmp_path, extra_config="""\
rate_limit:
  requests: 1
  window_seconds: 60
""")
    for _ in range(5):
        assert client.get("/healthz").status_code == 200


# --- Config validation ---

def test_invalid_rate_limit_type_fails(tmp_path):
    subscription_file = tmp_path / "s.yaml"
    app_config = tmp_path / "config.yaml"
    write_file(subscription_file, MIHOMO_CONFIG)
    write_file(
        app_config,
        f"""\
rate_limit: "10/minute"
somebody:
  url_prefix: "/x"
  config: "{subscription_file.as_posix()}"
""",
    )
    with pytest.raises(ConfigError, match="rate_limit must be a mapping"):
        create_app(str(app_config))


def test_invalid_allowed_user_agents_type_fails(tmp_path):
    subscription_file = tmp_path / "s.yaml"
    app_config = tmp_path / "config.yaml"
    write_file(subscription_file, MIHOMO_CONFIG)
    write_file(
        app_config,
        f"""\
allowed_user_agents: "clash*"
somebody:
  url_prefix: "/x"
  config: "{subscription_file.as_posix()}"
""",
    )
    with pytest.raises(ConfigError, match="allowed_user_agents must be a list"):
        create_app(str(app_config))
