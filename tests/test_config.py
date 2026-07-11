import pytest
from pydantic import ValidationError

from app.config import Settings


def test_test_urls_accepts_comma_separated_environment_value(monkeypatch) -> None:
    monkeypatch.setenv("SUBSCRIPTION_URL", "https://example.test/sub")
    monkeypatch.setenv("KUMA_URL", "http://kuma.test:3001")
    monkeypatch.setenv("KUMA_USERNAME", "user")
    monkeypatch.setenv("KUMA_PASSWORD", "password")
    monkeypatch.setenv(
        "TEST_URLS",
        "https://cp.cloudflare.com/generate_204, https://example.test/health",
    )

    settings = Settings(_env_file=None)

    assert settings.test_urls == [
        "https://cp.cloudflare.com/generate_204",
        "https://example.test/health",
    ]


def test_kuma_heartbeat_interval_must_exceed_probe_interval(monkeypatch) -> None:
    monkeypatch.setenv("SUBSCRIPTION_URL", "https://example.test/sub")
    monkeypatch.setenv("KUMA_URL", "http://kuma.test:3001")
    monkeypatch.setenv("KUMA_USERNAME", "user")
    monkeypatch.setenv("KUMA_PASSWORD", "password")
    monkeypatch.setenv("PROBE_INTERVAL", "60")
    monkeypatch.setenv("KUMA_HEARTBEAT_INTERVAL", "60")

    with pytest.raises(ValidationError, match="KUMA_HEARTBEAT_INTERVAL"):
        Settings(_env_file=None)


def test_kuma_heartbeat_interval_accepts_headroom(monkeypatch) -> None:
    monkeypatch.setenv("SUBSCRIPTION_URL", "https://example.test/sub")
    monkeypatch.setenv("KUMA_URL", "http://kuma.test:3001")
    monkeypatch.setenv("KUMA_USERNAME", "user")
    monkeypatch.setenv("KUMA_PASSWORD", "password")
    monkeypatch.setenv("PROBE_INTERVAL", "60")
    monkeypatch.setenv("KUMA_HEARTBEAT_INTERVAL", "75")

    assert Settings(_env_file=None).kuma_heartbeat_interval == 75


def test_kuma_monitor_group_is_configurable(monkeypatch) -> None:
    monkeypatch.setenv("SUBSCRIPTION_URL", "https://example.test/sub")
    monkeypatch.setenv("KUMA_URL", "http://kuma.test:3001")
    monkeypatch.setenv("KUMA_USERNAME", "user")
    monkeypatch.setenv("KUMA_PASSWORD", "password")
    monkeypatch.setenv("KUMA_MONITOR_GROUP", "Mossnet Nodes")

    assert Settings(_env_file=None).kuma_monitor_group == "Mossnet Nodes"
