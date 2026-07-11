import logging
from typing import Any

import httpx

from .socketio_client import KumaSocketIOClient

logger = logging.getLogger(__name__)


class StatusPageSync:
    """Uptime Kuma 2.x Status Page 的可选、失败隔离同步器。"""

    def __init__(
        self,
        socket: KumaSocketIOClient,
        slug: str,
        group_name: str = "Proxy Nodes",
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.socket, self.slug, self.group_name = socket, slug, group_name
        self.http_client = http_client

    async def _public_groups(self) -> list[dict[str, Any]]:
        path = f"/api/status-page/{self.slug}"
        if self.http_client is not None:
            response = await self.http_client.get(path)
        else:
            async with httpx.AsyncClient(
                base_url=self.socket.base_url,
                timeout=self.socket.timeout,
                verify=self.socket.tls_verify,
            ) as client:
                response = await client.get(path)
        response.raise_for_status()
        data = response.json()
        groups = data.get("publicGroupList", [])
        return groups if isinstance(groups, list) else []

    async def sync(self, active_monitor_ids: set[int], owned_monitor_ids: set[int]) -> None:
        if not self.slug:
            return
        try:
            result = await self.socket.call("getStatusPage", self.slug)
            config = result.get("config") or result
            groups = await self._public_groups()
            group = next((item for item in groups if item.get("name") == self.group_name), None)
            if group is None:
                group = {"name": self.group_name, "weight": len(groups) + 1, "monitorList": []}
                groups.append(group)
            current = [
                item
                for item in group.get("monitorList", [])
                if int(item.get("id", -1)) not in owned_monitor_ids
                or int(item.get("id", -1)) in active_monitor_ids
            ]
            existing = {int(item["id"]) for item in current if item.get("id")}
            group["monitorList"] = [
                *current,
                *({"id": item} for item in sorted(active_monitor_ids - existing)),
            ]
            saved = await self.socket.call("saveStatusPage", self.slug, config, "", groups)
            if not saved.get("ok"):
                raise RuntimeError("Kuma 未能保存 Status Page")
        except Exception as exc:
            logger.warning("status_page_sync_failed error=%s", type(exc).__name__)
