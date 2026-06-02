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


def test_serves_subscription_yaml(tmp_path):
    subscription_file = tmp_path / "somebody.yaml"
    app_config = tmp_path / "config.yaml"
    write_file(subscription_file, MIHOMO_CONFIG)
    write_file(
        app_config,
        f"""\
somebody:
  url_prefix: "/secret_path/secret_key"
  config: "{subscription_file.as_posix()}"
""",
    )

    client = TestClient(create_app(str(app_config)))

    response = client.get("/secret_path/secret_key")

    assert response.status_code == 200
    assert response.text == MIHOMO_CONFIG


def test_unknown_path_returns_404(tmp_path):
    subscription_file = tmp_path / "somebody.yaml"
    app_config = tmp_path / "config.yaml"
    write_file(subscription_file, MIHOMO_CONFIG)
    write_file(
        app_config,
        f"""\
somebody:
  url_prefix: "/secret_path/secret_key"
  config: "{subscription_file.as_posix()}"
""",
    )

    client = TestClient(create_app(str(app_config)))

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
    subscription_file = tmp_path / "somebody.yaml"
    app_config = tmp_path / "config.yaml"
    write_file(subscription_file, MIHOMO_CONFIG)
    write_file(
        app_config,
        f"""\
somebody:
  url_prefix: "/secret_path/secret_key"
  config: "{subscription_file.as_posix()}"
""",
    )

    client = TestClient(create_app(str(app_config)))

    response = client.get("/secret_path/secret_key")

    assert response.headers["content-type"] == "application/yaml"

