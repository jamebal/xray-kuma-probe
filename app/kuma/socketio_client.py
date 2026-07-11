import asyncio
from typing import Any

import socketio

from .models import KumaCompatibilityError


class KumaSocketIOClient:
    """集中封装 Uptime Kuma 2.x 的 Socket.IO ack 与 event 协议。"""

    def __init__(
        self, base_url: str, username: str, password: str, timeout: float, tls_verify: bool
    ) -> None:
        self.base_url, self.username, self.password, self.timeout = (
            base_url.rstrip("/"),
            username,
            password,
            timeout,
        )
        self.tls_verify = tls_verify
        self.client = socketio.AsyncClient(
            reconnection=True, ssl_verify=tls_verify, logger=False, engineio_logger=False
        )
        self._monitor_list: dict[str, dict[str, Any]] = {}
        self._monitor_list_ready = asyncio.Event()
        self.client.on("monitorList", self._on_monitor_list)
        self.client.on("updateMonitorIntoList", self._on_monitor_update)
        self.client.on("deleteMonitorFromList", self._on_monitor_delete)

    async def _on_monitor_list(self, data: dict[str, dict[str, Any]]) -> None:
        self._monitor_list = data
        self._monitor_list_ready.set()

    async def _on_monitor_update(self, data: dict[str, dict[str, Any]]) -> None:
        self._monitor_list.update(data)
        self._monitor_list_ready.set()

    async def _on_monitor_delete(self, monitor_id: int) -> None:
        self._monitor_list.pop(str(monitor_id), None)

    async def get_monitor_list(self) -> dict[str, dict[str, Any]]:
        self._monitor_list_ready.clear()
        result = await self.call("getMonitorList")
        if not result.get("ok"):
            raise KumaCompatibilityError("Kuma 未能返回 Monitor 列表")
        await asyncio.wait_for(self._monitor_list_ready.wait(), self.timeout)
        return self._monitor_list.copy()

    async def connect(self) -> None:
        if not self.client.connected:
            await self.client.connect(
                self.base_url, transports=["websocket", "polling"], wait_timeout=self.timeout
            )
        await self.login()

    async def login(self) -> None:
        result = await self.call(
            "login", {"username": self.username, "password": self.password, "token": ""}
        )
        if not result.get("ok"):
            raise PermissionError("Uptime Kuma 登录失败")

    async def call(self, event: str, *args: object) -> dict[str, Any]:
        try:
            result = await asyncio.wait_for(self.client.call(event, data=args), self.timeout)
        except (TimeoutError, socketio.exceptions.SocketIOError) as exc:
            raise ConnectionError(f"Kuma API 调用失败: {event}") from exc
        if not isinstance(result, dict):
            raise KumaCompatibilityError(f"Kuma event {event} 返回了未知格式")
        return result

    async def disconnect(self) -> None:
        if self.client.connected:
            await self.client.disconnect()
