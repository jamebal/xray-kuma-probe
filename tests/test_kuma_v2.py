from typing import Any

import httpx
import pytest

from app.kuma.client import KumaManagementClient
from app.kuma.models import KumaMonitor
from app.kuma.status_page import StatusPageSync


class FakeSocket:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.monitors: dict[str, dict[str, Any]] = {
            "7": {
                "id": 7,
                "name": "old",
                "type": "push",
                "pushToken": "push-token",
                "active": True,
                "accepted_statuscodes": ["200-299"],
                "conditions": [],
                "kafkaProducerBrokers": [],
                "kafkaProducerSaslOptions": {"mechanism": "None"},
                "rabbitmqNodes": [],
                "notificationIDList": {},
            }
        }

    async def connect(self) -> None:
        return None

    async def disconnect(self) -> None:
        return None

    async def get_monitor_list(self) -> dict[str, dict[str, Any]]:
        return self.monitors

    async def call(self, event: str, *args: object) -> dict[str, Any]:
        self.calls.append((event, args))
        if event == "add":
            return {"ok": True, "monitorID": 7}
        return {"ok": True}


@pytest.mark.asyncio
async def test_v2_monitor_list_comes_from_socket_event_cache() -> None:
    client = KumaManagementClient(FakeSocket())  # type: ignore[arg-type]
    monitors = await client.list_monitors()
    assert monitors == [KumaMonitor(7, "old", "push-token", True, monitors[0].raw)]


@pytest.mark.asyncio
async def test_v2_create_payload_contains_required_collection_fields() -> None:
    socket = FakeSocket()
    client = KumaManagementClient(socket)  # type: ignore[arg-type]
    await client.create_push_monitor("node", 60, parent_id=9)
    payload = socket.calls[0][1][0]
    assert isinstance(payload, dict)
    assert payload["accepted_statuscodes"] == ["200-299"]
    assert payload["conditions"] == []
    assert payload["kafkaProducerBrokers"] == []
    assert payload["kafkaProducerSaslOptions"] == {"mechanism": "None"}
    assert payload["rabbitmqNodes"] == []
    assert len(payload["pushToken"]) == 32
    assert payload["parent"] == 9


@pytest.mark.asyncio
async def test_v2_creates_real_group_monitor_payload() -> None:
    socket = FakeSocket()
    client = KumaManagementClient(socket)  # type: ignore[arg-type]
    await client.create_group_monitor("Proxy Nodes")
    payload = socket.calls[0][1][0]
    assert isinstance(payload, dict)
    assert payload["type"] == "group"
    assert payload["name"] == "Proxy Nodes"
    assert payload["parent"] is None


@pytest.mark.asyncio
async def test_v2_update_preserves_full_monitor_payload() -> None:
    socket = FakeSocket()
    client = KumaManagementClient(socket)  # type: ignore[arg-type]
    monitor = (await client.list_monitors())[0]
    await client.update_monitor(monitor, "new", 120, parent_id=9)
    payload = socket.calls[-1][1][0]
    assert isinstance(payload, dict)
    assert payload["name"] == "new"
    assert payload["interval"] == 120
    assert payload["accepted_statuscodes"] == ["200-299"]
    assert payload["conditions"] == []
    assert payload["parent"] == 9


@pytest.mark.asyncio
async def test_v2_status_page_uses_rest_groups_and_full_save_signature() -> None:
    socket = FakeSocket()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/status-page/mossnet-status"
        return httpx.Response(
            200,
            json={
                "publicGroupList": [
                    {"id": 2, "name": "Proxy Nodes", "monitorList": [{"id": 99}]}
                ]
            },
        )

    http = httpx.AsyncClient(
        base_url="http://kuma.example", transport=httpx.MockTransport(handler)
    )
    sync = StatusPageSync(socket, "mossnet-status", http_client=http)  # type: ignore[arg-type]
    await sync.sync({7}, {7})
    event, args = socket.calls[-1]
    assert event == "saveStatusPage"
    assert args[0] == "mossnet-status"
    assert args[2] == ""
    assert args[3][0]["monitorList"] == [{"id": 99}, {"id": 7}]
    await http.aclose()
