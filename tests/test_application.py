import logging
from types import SimpleNamespace

import pytest

from app.main import Application
from app.utils.hashing import stable_hash

from .test_subscription import TROJAN, VLESS


class FakeFetcher:
    async def fetch(self, url: str) -> str:
        return f"{VLESS}\n{TROJAN}"


class FakeRepository:
    def __init__(self) -> None:
        self.upserted_names: list[str] = []
        self.disabled_keys: set[str] = set()
        self.active_keys: set[str] = set()

    async def upsert_node(self, node):
        self.upserted_names.append(node.display_name)
        return SimpleNamespace(socks_port=20000)

    async def disable_nodes(self, node_keys: set[str]) -> None:
        self.disabled_keys = node_keys

    async def mark_missing(self, active_keys: set[str], grace_period: int) -> None:
        self.active_keys = active_keys

    async def list_nodes(self):
        return []


class FakeStatusPage:
    async def sync(self, active_ids: set[int], owned_ids: set[int]) -> None:
        return None


class FakeXray:
    def __init__(self) -> None:
        self.installed_config = None
        self.restarted = False

    async def install_config(self, config) -> bool:
        self.installed_config = config
        return True

    async def restart(self) -> None:
        self.restarted = True


class FakeReconciler:
    def __init__(self, *args) -> None:
        pass

    async def reconcile(self, records) -> None:
        return None


def make_application(keywords: list[str]) -> Application:
    app = object.__new__(Application)
    app.settings = SimpleNamespace(
        subscription_url="https://example.test/sub",
        node_exclude_keywords=keywords,
        removed_node_grace_period=86400,
        monitor_name_prefix="Proxy",
        kuma_heartbeat_interval=75,
        removed_node_policy="pause",
        kuma_monitor_group="Proxy Nodes",
    )
    app.fetcher = FakeFetcher()
    app.repository = FakeRepository()
    app.management = object()
    app.status_page = FakeStatusPage()
    app.xray = FakeXray()
    app.last_subscription_success = None
    app.nodes = {}
    app.subscription_hash = None
    return app


@pytest.mark.asyncio
async def test_sync_subscription_excludes_matching_nodes_and_disables_existing(
    monkeypatch,
) -> None:
    monkeypatch.setattr("app.main.KumaReconciler", FakeReconciler)
    app = make_application(["la"])

    await app.sync_subscription(force=True)

    assert app.repository.upserted_names == ["Tokyo"]
    assert app.repository.disabled_keys == {"vless:🇺🇸 LA"}
    assert app.repository.active_keys == {"trojan:Tokyo"}
    assert len(app.xray.installed_config["inbounds"]) == 1
    assert app.xray.installed_config["outbounds"][0]["settings"]["servers"][0][
        "address"
    ] == "2001:db8::1"
    assert app.xray.restarted is True


@pytest.mark.asyncio
async def test_sync_subscription_accepts_valid_subscription_when_all_nodes_are_filtered(
    monkeypatch,
) -> None:
    monkeypatch.setattr("app.main.KumaReconciler", FakeReconciler)
    app = make_application(["la", "tokyo"])

    await app.sync_subscription(force=True)

    assert app.repository.upserted_names == []
    assert app.repository.disabled_keys == {"vless:🇺🇸 LA", "trojan:Tokyo"}
    assert app.repository.active_keys == set()
    assert app.xray.installed_config["inbounds"] == []
    assert app.xray.installed_config["outbounds"] == []


@pytest.mark.asyncio
async def test_unchanged_subscription_logs_included_and_excluded_counts(
    monkeypatch, caplog
) -> None:
    monkeypatch.setattr("app.main.KumaReconciler", FakeReconciler)
    app = make_application(["la"])
    app.subscription_hash = stable_hash(f"{VLESS}\n{TROJAN}")

    with caplog.at_level(logging.INFO):
        await app.sync_subscription()

    assert "nodes=1 excluded=1 changed=false" in caplog.text
