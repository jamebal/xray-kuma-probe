import asyncio
import logging

from app.kuma.push_client import KumaPushClient
from app.state.repository import NodeRecord, NodeRepository

from .checker import ProbeChecker

logger = logging.getLogger(__name__)


class ProbeScheduler:
    def __init__(
        self,
        repository: NodeRepository,
        checker: ProbeChecker,
        push: KumaPushClient,
        urls: list[str],
        concurrency: int,
        failure_threshold: int,
        recovery_threshold: int,
    ) -> None:
        self.repository, self.checker, self.push, self.urls = repository, checker, push, urls
        self.semaphore = asyncio.Semaphore(concurrency)
        self.failure_threshold, self.recovery_threshold = failure_threshold, recovery_threshold

    async def run_once(self) -> None:
        await asyncio.gather(
            *(self._probe(node) for node in await self.repository.list_nodes(active_only=True)),
            return_exceptions=False,
        )

    async def _probe(self, node: NodeRecord) -> None:
        async with self.semaphore:
            result = await self.checker.check(node.socks_port, self.urls)
        status = await self.repository.record_probe(
            node.node_key, result.success, self.failure_threshold, self.recovery_threshold
        )
        logger.info(
            "probe_%s node=%r latency_ms=%s error=%s",
            "success" if result.success else "failed",
            node.display_name,
            result.total_time_ms,
            result.error_category,
        )
        if node.kuma_push_token:
            try:
                await self.push.push(
                    node.kuma_push_token,
                    "up" if status == "up" else "down",
                    result.total_time_ms,
                    result.message,
                )
            except ConnectionError:
                logger.error("kuma_push_failed node=%r", node.display_name)
