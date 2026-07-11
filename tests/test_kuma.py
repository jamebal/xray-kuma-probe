from dataclasses import replace

import pytest

from app.kuma.models import KumaMonitor
from app.kuma.reconciler import KumaReconciler
from app.state.database import Database
from app.state.repository import NodeRepository
from app.subscription.parser import parse_subscription

from .test_subscription import VLESS


class FakeManagement:
    def __init__(self) -> None:
        self.created = 0
        self.intervals: list[int] = []
        self.paused: list[int] = []
        self.group_created = 0
        self.parents: list[int | None] = []
        self.group: KumaMonitor | None = None
        self.children: list[KumaMonitor] = []

    async def list_monitors(self) -> list[KumaMonitor]:
        monitors = [
            KumaMonitor(id=999, name="[Proxy] foreign", push_token="foreign", active=True)
        ]
        if self.group is not None:
            monitors.append(self.group)
        monitors.extend(self.children)
        return monitors

    async def create_push_monitor(
        self, name: str, interval: int, parent_id: int | None = None
    ) -> KumaMonitor:
        self.created += 1
        self.intervals.append(interval)
        self.parents.append(parent_id)
        child = KumaMonitor(
            id=10,
            name=name,
            push_token="token",
            active=True,
            raw={"id": 10, "name": name, "type": "push", "parent": parent_id},
        )
        self.children.append(child)
        return child

    async def create_group_monitor(self, name: str) -> KumaMonitor:
        self.group_created += 1
        self.group = KumaMonitor(
            id=20,
            name=name,
            push_token="",
            active=True,
            raw={"id": 20, "name": name, "type": "group", "parent": None},
        )
        return self.group

    async def update_monitor(
        self,
        monitor: KumaMonitor,
        name: str,
        interval: int,
        active: bool = True,
        parent_id: int | None = None,
    ) -> None:
        self.parents.append(parent_id)
        return None

    async def pause_monitor(self, monitor_id: int) -> None:
        self.paused.append(monitor_id)

    async def delete_monitor(self, monitor_id: int) -> None:
        return None


@pytest.mark.asyncio
async def test_reconcile_creates_once_and_never_touches_foreign(tmp_path) -> None:
    db = Database(tmp_path / "state.db")
    await db.initialize()
    repo = NodeRepository(db, 20000, 20010)
    node = await repo.upsert_node(parse_subscription(VLESS).nodes[0])
    client = FakeManagement()
    reconciler = KumaReconciler(client, repo, "Proxy", 75, "pause", "Proxy Nodes")
    await reconciler.reconcile([node])
    owned = (await repo.list_nodes())[0]
    await reconciler.reconcile([owned])
    await reconciler.reconcile([replace(owned, enabled=False)])
    assert client.created == 1
    assert client.group_created == 1
    assert client.intervals == [75]
    assert client.parents[0] == 20
    assert client.paused == [10]
    await db.close()


@pytest.mark.asyncio
async def test_reconcile_recreates_missing_owned_monitor_inside_group(tmp_path) -> None:
    db = Database(tmp_path / "state.db")
    await db.initialize()
    repo = NodeRepository(db, 20000, 20010)
    node = await repo.upsert_node(parse_subscription(VLESS).nodes[0])
    await repo.set_kuma(node.node_key, 404, "stale-token")
    stale = (await repo.list_nodes())[0]
    client = FakeManagement()

    await KumaReconciler(
        client, repo, "Proxy", 75, "pause", "Proxy Nodes"
    ).reconcile([stale])

    restored = (await repo.list_nodes())[0]
    assert restored.kuma_monitor_id == 10
    assert restored.kuma_push_token == "token"
    assert client.parents == [20]
    await db.close()
