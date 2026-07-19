import asyncio
import ssl
import time
from datetime import UTC, datetime

import httpx

from .models import ErrorCategory, ProbeResult


def _category(exc: Exception) -> ErrorCategory:
    text = str(exc).lower()
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return "TIMEOUT"
    if isinstance(exc, ssl.SSLError) or "tls" in text or "certificate" in text:
        return "TLS_FAILED"
    if "socks" in text:
        return "SOCKS_FAILED"
    if "name or service" in text or "nodename" in text:
        return "DNS_FAILED"
    if isinstance(exc, httpx.ConnectError):
        return "CONNECT_FAILED"
    if isinstance(exc, httpx.ProxyError):
        return "PROXY_FAILED"
    return "UNKNOWN"


class ProbeChecker:
    def __init__(self, timeout: float, connect_timeout: float, tls_verify: bool) -> None:
        self.timeout = httpx.Timeout(timeout, connect=connect_timeout)
        self.tls_verify = tls_verify

    async def check(self, socks_port: int, urls: list[str]) -> ProbeResult:
        try:
            latencies: list[float] = []
            last_status: int | None = None
            async with httpx.AsyncClient(
                proxy=f"socks5://127.0.0.1:{socks_port}",
                timeout=self.timeout,
                verify=self.tls_verify,
                follow_redirects=True,
            ) as client:
                for url in urls:
                    started = time.perf_counter()
                    response = await client.get(url)
                    elapsed_ms = (time.perf_counter() - started) * 1000
                    last_status = response.status_code
                    expected = (
                        response.status_code == 204
                        if "generate_204" in url
                        else 200 <= response.status_code < 400
                    )
                    if not expected:
                        return ProbeResult(
                            False,
                            None,
                            response.status_code,
                            "HTTP_ERROR",
                            datetime.now(UTC),
                        )
                    latencies.append(elapsed_ms)
            return ProbeResult(
                True,
                round(sum(latencies) / len(latencies)),
                last_status,
                None,
                datetime.now(UTC),
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            return ProbeResult(False, None, None, _category(exc), datetime.now(UTC))
