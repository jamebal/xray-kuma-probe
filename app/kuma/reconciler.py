from typing import Protocol

from app.state.repository import NodeRecord, NodeRepository

from .models import KumaMonitor


class ManagementAdapter(Protocol):
    async def list_monitors(self) -> list[KumaMonitor]: ...
    async def create_push_monitor(
        self, name: str, interval: int, parent_id: int | None = None
    ) -> KumaMonitor: ...
    async def create_group_monitor(self, name: str) -> KumaMonitor: ...
    async def update_monitor(
        self,
        monitor: KumaMonitor,
        name: str,
        interval: int,
        active: bool = True,
        parent_id: int | None = None,
    ) -> None: ...
    async def pause_monitor(self, monitor_id: int) -> None: ...
    async def delete_monitor(self, monitor_id: int) -> None: ...


class KumaReconciler:
    def __init__(
        self,
        client: ManagementAdapter,
        repository: NodeRepository,
        prefix: str,
        interval: int,
        removed_policy: str,
        group_name: str,
    ) -> None:
        self.client, self.repository, self.prefix, self.interval, self.removed_policy = (
            client,
            repository,
            prefix,
            interval,
            removed_policy,
        )
        self.group_name = group_name.strip()

    async def _ensure_group(self, monitors: dict[int, KumaMonitor]) -> int | None:
        if not self.group_name:
            return None
        stored_id = await self.repository.get_kuma_group_id()
        stored = monitors.get(stored_id) if stored_id is not None else None
        if stored is not None and stored.raw.get("type") == "group":
            if stored.name != self.group_name:
                await self.client.update_monitor(stored, self.group_name, 60, True, None)
            return stored.id
        created = await self.client.create_group_monitor(self.group_name)
        await self.repository.set_kuma_group_id(created.id)
        monitors[created.id] = created
        return created.id

    async def reconcile(self, nodes: list[NodeRecord]) -> None:
        monitors = {item.id: item for item in await self.client.list_monitors()}
        group_id = await self._ensure_group(monitors)
        for node in nodes:
            name = f"[{self.prefix}] {node.display_name}"
            owned = (
                monitors.get(node.kuma_monitor_id)
                if node.kuma_monitor_id is not None
                else None
            )
            if node.enabled and owned is None:
                created = await self.client.create_push_monitor(name, self.interval, group_id)
                await self.repository.set_kuma(node.node_key, created.id, created.push_token)
                continue
            if node.kuma_monitor_id is None:
                continue
            if not node.enabled:
                if self.removed_policy == "delete":
                    await self.client.delete_monitor(node.kuma_monitor_id)
                else:
                    await self.client.pause_monitor(node.kuma_monitor_id)
            elif owned is not None:
                await self.client.update_monitor(owned, name, self.interval, True, group_id)
