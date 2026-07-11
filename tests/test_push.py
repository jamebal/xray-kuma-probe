from pathlib import Path

import httpx
import pytest

from app.kuma.push_client import KumaPushClient
from app.xray.manager import XrayManager


@pytest.mark.asyncio
async def test_push_retries_and_encodes_token() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        assert request.url.raw_path.split(b"?", 1)[0] == b"/api/push/a%2Fb"
        return httpx.Response(503 if attempts == 1 else 200)

    client = KumaPushClient("https://kuma.example", 1, 2, True)
    await client.client.aclose()
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await client.push("a/b", "down", None, "TIMEOUT")
    assert attempts == 2
    await client.close()


@pytest.mark.asyncio
async def test_xray_config_is_replaced_only_after_validation(tmp_path: Path) -> None:
    binary = tmp_path / "xray"
    binary.write_text("#!/bin/sh\ncase \"$*\" in *bad*) exit 1;; *) exit 0;; esac\n")
    binary.chmod(0o755)
    target = tmp_path / "xray.json"
    manager = XrayManager(binary, target)
    assert await manager.install_config({"marker": "good"})
    previous = target.read_text()
    binary.write_text("#!/bin/sh\nexit 1\n")
    assert not await manager.install_config({"marker": "bad"})
    assert target.read_text() == previous
