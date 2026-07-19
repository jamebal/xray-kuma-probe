from types import SimpleNamespace

import httpx
import pytest

from app.probe.checker import ProbeChecker


class FakeAsyncClient:
    def __init__(self, outcomes: list[int | Exception]) -> None:
        self.outcomes = outcomes
        self.requested_urls: list[str] = []

    def factory(self, **kwargs):
        owner = self

        class Context:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, traceback) -> None:
                return None

            async def get(self, url: str):
                owner.requested_urls.append(url)
                outcome = owner.outcomes[len(owner.requested_urls) - 1]
                if isinstance(outcome, Exception):
                    raise outcome
                return SimpleNamespace(status_code=outcome)

        return Context()


@pytest.mark.asyncio
async def test_check_requests_every_url_and_returns_average_latency(monkeypatch) -> None:
    client = FakeAsyncClient([204, 200])
    monkeypatch.setattr("app.probe.checker.httpx.AsyncClient", client.factory)
    times = iter([1.0, 1.1, 2.0, 2.3])
    monkeypatch.setattr("app.probe.checker.time.perf_counter", lambda: next(times))

    result = await ProbeChecker(10, 5, True).check(
        20000,
        [
            "https://cp.cloudflare.com/generate_204",
            "https://example.test/health",
        ],
    )

    assert client.requested_urls == [
        "https://cp.cloudflare.com/generate_204",
        "https://example.test/health",
    ]
    assert result.success is True
    assert result.total_time_ms == 200
    assert result.status_code == 200


@pytest.mark.asyncio
async def test_check_fails_when_any_url_has_unexpected_status(monkeypatch) -> None:
    client = FakeAsyncClient([204, 500])
    monkeypatch.setattr("app.probe.checker.httpx.AsyncClient", client.factory)
    times = iter([1.0, 1.1, 2.0, 2.3])
    monkeypatch.setattr("app.probe.checker.time.perf_counter", lambda: next(times))

    result = await ProbeChecker(10, 5, True).check(
        20000,
        [
            "https://cp.cloudflare.com/generate_204",
            "https://example.test/health",
        ],
    )

    assert result.success is False
    assert result.total_time_ms is None
    assert result.status_code == 500
    assert result.error_category == "HTTP_ERROR"


@pytest.mark.asyncio
async def test_check_fails_without_partial_average_when_later_url_raises(monkeypatch) -> None:
    request = httpx.Request("GET", "https://example.test/health")
    client = FakeAsyncClient([204, httpx.ReadTimeout("timeout", request=request)])
    monkeypatch.setattr("app.probe.checker.httpx.AsyncClient", client.factory)
    times = iter([1.0, 1.1, 2.0])
    monkeypatch.setattr("app.probe.checker.time.perf_counter", lambda: next(times))

    result = await ProbeChecker(10, 5, True).check(
        20000,
        [
            "https://cp.cloudflare.com/generate_204",
            "https://example.test/health",
        ],
    )

    assert client.requested_urls == [
        "https://cp.cloudflare.com/generate_204",
        "https://example.test/health",
    ]
    assert result.success is False
    assert result.total_time_ms is None
    assert result.error_category == "TIMEOUT"


@pytest.mark.asyncio
async def test_check_single_url_returns_that_url_latency(monkeypatch) -> None:
    client = FakeAsyncClient([204])
    monkeypatch.setattr("app.probe.checker.httpx.AsyncClient", client.factory)
    times = iter([1.0, 1.125])
    monkeypatch.setattr("app.probe.checker.time.perf_counter", lambda: next(times))

    result = await ProbeChecker(10, 5, True).check(
        20000, ["https://cp.cloudflare.com/generate_204"]
    )

    assert result.success is True
    assert result.total_time_ms == 125
