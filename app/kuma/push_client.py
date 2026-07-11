import asyncio
from typing import Literal
from urllib.parse import quote

import httpx


class KumaPushClient:
    def __init__(self, base_url: str, timeout: float, retries: int, tls_verify: bool) -> None:
        self.base_url, self.retries = base_url.rstrip("/"), retries
        self.client = httpx.AsyncClient(timeout=timeout, verify=tls_verify)

    async def push(
        self, push_token: str, status: Literal["up", "down"], ping_ms: int | None, message: str
    ) -> None:
        url = f"{self.base_url}/api/push/{quote(push_token, safe='')}"
        params: dict[str, str | int] = {"status": status, "msg": message[:250]}
        if ping_ms is not None:
            params["ping"] = max(0, ping_ms)
        error: Exception | None = None
        for attempt in range(self.retries):
            try:
                response = await self.client.get(url, params=params)
                response.raise_for_status()
                return
            except httpx.HTTPError as exc:
                error = exc
                if attempt + 1 < self.retries:
                    await asyncio.sleep(0.25 * 2**attempt)
        raise ConnectionError("Kuma Push 失败") from error

    async def close(self) -> None:
        await self.client.aclose()
