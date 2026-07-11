import httpx


class SubscriptionFetcher:
    def __init__(self, timeout: float, tls_verify: bool) -> None:
        self._client = httpx.AsyncClient(timeout=timeout, verify=tls_verify, follow_redirects=True)

    async def fetch(self, url: str) -> str:
        response = await self._client.get(url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        text = response.text
        if not text.strip() or "text/html" in content_type or "<html" in text[:256].lower():
            raise ValueError("订阅响应为空或不是节点订阅")
        return text

    async def close(self) -> None:
        await self._client.aclose()
