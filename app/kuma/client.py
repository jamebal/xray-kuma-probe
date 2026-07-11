import secrets
from typing import Any

from .models import KumaCompatibilityError, KumaMonitor
from .socketio_client import KumaSocketIOClient


class KumaManagementClient:
    def __init__(self, socket: KumaSocketIOClient) -> None:
        self.socket = socket

    async def connect(self) -> None:
        await self.socket.connect()

    async def close(self) -> None:
        await self.socket.disconnect()

    async def list_monitors(self) -> list[KumaMonitor]:
        raw = await self.socket.get_monitor_list()
        items = list(raw.values())
        return [self._monitor(item) for item in items if isinstance(item, dict)]

    def _monitor(self, item: dict[str, Any]) -> KumaMonitor:
        return KumaMonitor(
            int(item["id"]),
            str(item.get("name", "")),
            str(item.get("pushToken", "")),
            bool(item.get("active", True)),
            item.copy(),
        )

    def _monitor_payload(
        self, monitor_type: str, name: str, interval: int, parent_id: int | None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": monitor_type,
            "name": name,
            "parent": parent_id,
            "interval": interval,
            "retryInterval": interval,
            "resendInterval": 0,
            "maxretries": 0,
            "active": True,
            "notificationIDList": {},
            "accepted_statuscodes": ["200-299"],
            "conditions": [],
            "kafkaProducerBrokers": [],
            "kafkaProducerSaslOptions": {"mechanism": "None"},
            "rabbitmqNodes": [],
        }
        if monitor_type == "push":
            payload["pushToken"] = secrets.token_urlsafe(24)
        return payload

    async def _create_monitor(self, payload: dict[str, Any]) -> KumaMonitor:
        result = await self.socket.call("add", payload)
        if not result.get("ok") or not result.get("monitorID"):
            raise KumaCompatibilityError("Kuma 未能创建 Push Monitor")
        monitor_id = int(result["monitorID"])
        monitors = await self.list_monitors()
        found = next((item for item in monitors if item.id == monitor_id), None)
        if not found:
            raise KumaCompatibilityError("已创建 Monitor，但 Kuma 未返回 Monitor 配置")
        return found

    async def create_push_monitor(
        self, name: str, interval: int, parent_id: int | None = None
    ) -> KumaMonitor:
        monitor = await self._create_monitor(
            self._monitor_payload("push", name, interval, parent_id)
        )
        if not monitor.push_token:
            raise KumaCompatibilityError("已创建 Monitor，但 Kuma 未返回 Push Token")
        return monitor

    async def create_group_monitor(self, name: str) -> KumaMonitor:
        return await self._create_monitor(self._monitor_payload("group", name, 60, None))

    async def update_monitor(
        self,
        monitor: KumaMonitor,
        name: str,
        interval: int,
        active: bool = True,
        parent_id: int | None = None,
    ) -> None:
        payload = monitor.raw.copy()
        if not payload:
            raise KumaCompatibilityError("缺少 Monitor 完整配置，拒绝执行覆盖式更新")
        payload.update(name=name, interval=interval, active=active, parent=parent_id)
        result = await self.socket.call("editMonitor", payload)
        if not result.get("ok"):
            raise KumaCompatibilityError("Kuma 未能更新 Monitor")

    async def pause_monitor(self, monitor_id: int) -> None:
        await self.socket.call("pauseMonitor", monitor_id)

    async def delete_monitor(self, monitor_id: int) -> None:
        await self.socket.call("deleteMonitor", monitor_id)
