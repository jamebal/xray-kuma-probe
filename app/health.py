from collections.abc import Awaitable, Callable

from aiohttp import web


class HealthServer:
    def __init__(
        self, host: str, port: int, status: Callable[[], Awaitable[dict[str, object]]]
    ) -> None:
        self.host, self.port, self.status = host, port, status
        self.runner: web.AppRunner | None = None

    async def start(self) -> None:
        app = web.Application()
        app.router.add_get("/health", self._health)
        self.runner = web.AppRunner(app, access_log=None)
        await self.runner.setup()
        await web.TCPSite(self.runner, self.host, self.port).start()

    async def _health(self, request: web.Request) -> web.Response:
        return web.json_response(await self.status())

    async def close(self) -> None:
        if self.runner:
            await self.runner.cleanup()
