from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings


@pytest.fixture(autouse=True)
def required_settings(monkeypatch) -> None:
    monkeypatch.setenv("SUBSCRIPTION_URL", "https://example.test/sub")
    monkeypatch.setenv("KUMA_URL", "http://kuma.test:3001")
    monkeypatch.setenv("KUMA_USERNAME", "user")
    monkeypatch.setenv("KUMA_PASSWORD", "password")


def test_test_urls_accepts_comma_separated_environment_value(monkeypatch) -> None:
    monkeypatch.setenv(
        "TEST_URLS",
        "https://cp.cloudflare.com/generate_204, https://example.test/health",
    )

    settings = Settings(_env_file=None)

    assert settings.test_urls == [
        "https://cp.cloudflare.com/generate_204",
        "https://example.test/health",
    ]


def test_node_exclude_keywords_accept_comma_separated_value(monkeypatch) -> None:
    monkeypatch.setenv("NODE_EXCLUDE_KEYWORDS", " Expire, 官网, ,剩余流量 ")

    settings = Settings(_env_file=None)

    assert settings.node_exclude_keywords == ["Expire", "官网", "剩余流量"]


def test_node_exclude_keywords_default_to_empty_list() -> None:
    assert Settings(_env_file=None).node_exclude_keywords == []


def test_test_urls_rejects_empty_environment_value(monkeypatch) -> None:
    monkeypatch.setenv("TEST_URLS", " , ")

    with pytest.raises(ValidationError, match="TEST_URLS"):
        Settings(_env_file=None)


def test_kuma_heartbeat_interval_must_exceed_probe_interval(monkeypatch) -> None:
    monkeypatch.setenv("PROBE_INTERVAL", "60")
    monkeypatch.setenv("KUMA_HEARTBEAT_INTERVAL", "60")

    with pytest.raises(ValidationError, match="KUMA_HEARTBEAT_INTERVAL"):
        Settings(_env_file=None)


def test_kuma_heartbeat_interval_accepts_headroom(monkeypatch) -> None:
    monkeypatch.setenv("PROBE_INTERVAL", "60")
    monkeypatch.setenv("KUMA_HEARTBEAT_INTERVAL", "75")

    assert Settings(_env_file=None).kuma_heartbeat_interval == 75


def test_kuma_monitor_group_is_configurable(monkeypatch) -> None:
    monkeypatch.setenv("KUMA_MONITOR_GROUP", "Mossnet Nodes")

    assert Settings(_env_file=None).kuma_monitor_group == "Mossnet Nodes"


def test_env_example_documents_node_filter_and_multiple_test_urls() -> None:
    example = Path(".env.example").read_text()

    assert "NODE_EXCLUDE_KEYWORDS=" in example
    test_urls_line = next(
        line for line in example.splitlines() if line.startswith("TEST_URLS=")
    )
    assert "," in test_urls_line
