import asyncio
import contextlib
import logging
import signal
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from app.config import Settings
from app.health import HealthServer
from app.kuma.client import KumaManagementClient
from app.kuma.push_client import KumaPushClient
from app.kuma.reconciler import KumaReconciler
from app.kuma.socketio_client import KumaSocketIOClient
from app.kuma.status_page import StatusPageSync
from app.probe.checker import ProbeChecker
from app.probe.scheduler import ProbeScheduler
from app.state.database import Database
from app.state.repository import NodeRepository
from app.subscription.fetcher import SubscriptionFetcher
from app.subscription.filter import partition_nodes
from app.subscription.models import ProxyNode
from app.subscription.parser import parse_subscription
from app.utils.hashing import stable_hash
from app.utils.logging import configure_logging
from app.xray.config_builder import build_config
from app.xray.manager import XrayManager

logger = logging.getLogger(__name__)


async def run_fixed_interval(
    action: Callable[[], Awaitable[None]], interval: float, stop_event: asyncio.Event
) -> None:
    loop = asyncio.get_running_loop()
    next_run = loop.time()
    while not stop_event.is_set():
        await action()
        if stop_event.is_set():
            return
        next_run += interval
        now = loop.time()
        if now - next_run >= interval:
            next_run = now
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop_event.wait(), max(0.0, next_run - now))


class Application:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.database = Database(settings.database_path)
        self.repository = NodeRepository(
            self.database, settings.socks_port_start, settings.socks_port_end
        )
        self.fetcher = SubscriptionFetcher(settings.probe_timeout, settings.tls_verify)
        socket = KumaSocketIOClient(
            settings.kuma_url,
            settings.kuma_username,
            settings.kuma_password,
            settings.kuma_timeout,
            settings.tls_verify,
        )
        self.management = KumaManagementClient(socket)
        self.status_page = StatusPageSync(socket, settings.kuma_status_page_slug)
        self.push = KumaPushClient(
            settings.kuma_url, settings.kuma_timeout, settings.kuma_retries, settings.tls_verify
        )
        self.xray = XrayManager(settings.xray_binary, settings.xray_config)
        self.probes = ProbeScheduler(
            self.repository,
            ProbeChecker(
                settings.probe_timeout, settings.probe_connect_timeout, settings.tls_verify
            ),
            self.push,
            settings.test_urls,
            settings.probe_concurrency,
            settings.failure_threshold,
            settings.recovery_threshold,
        )
        self.health = HealthServer(settings.health_listen, settings.health_port, self.health_status)
        self.stop_event = asyncio.Event()
        self.last_subscription_success: datetime | None = None
        self.nodes: dict[str, ProxyNode] = {}
        self.subscription_hash: str | None = None

    async def start(self) -> None:
        await self.database.initialize()
        await self.health.start()
        await self.management.connect()
        await self.sync_subscription(force=True)
        await self.xray.start()
        await asyncio.gather(self._probe_loop(), self._subscription_loop(), self.stop_event.wait())

    async def sync_subscription(self, force: bool = False) -> None:
        try:
            content = await self.fetcher.fetch(self.settings.subscription_url)
            parsed = parse_subscription(content)
            if not parsed.nodes:
                raise ValueError("订阅中没有有效的 VLESS 或 Trojan 节点")
        except Exception as exc:
            logger.error("subscription_fetch_failed error=%s", type(exc).__name__)
            if force and not self.nodes:
                raise
            return
        content_hash = stable_hash(content)
        self.last_subscription_success = datetime.now(UTC)
        if content_hash == self.subscription_hash and not force:
            logger.info("subscription_sync_success nodes=%d changed=false", len(parsed.nodes))
            return
        nodes, excluded_nodes = partition_nodes(
            parsed.nodes, self.settings.node_exclude_keywords
        )
        records = [await self.repository.upsert_node(node) for node in nodes]
        await self.repository.disable_nodes({node.node_key for node in excluded_nodes})
        await self.repository.mark_missing(
            {node.node_key for node in nodes}, self.settings.removed_node_grace_period
        )
        all_records = await self.repository.list_nodes()
        try:
            await KumaReconciler(
                self.management,
                self.repository,
                self.settings.monitor_name_prefix,
                self.settings.kuma_heartbeat_interval,
                self.settings.removed_node_policy,
                self.settings.kuma_monitor_group,
            ).reconcile(all_records)
            refreshed = await self.repository.list_nodes()
            owned_ids = {
                item.kuma_monitor_id for item in refreshed if item.kuma_monitor_id is not None
            }
            active_ids = {
                item.kuma_monitor_id
                for item in refreshed
                if item.enabled and item.kuma_monitor_id is not None
            }
            await self.status_page.sync(active_ids, owned_ids)
        except Exception as exc:
            logger.error("kuma_reconcile_failed error=%s", type(exc).__name__)
        config = build_config(
            [(node, record.socks_port) for node, record in zip(nodes, records, strict=True)]
        )
        if not await self.xray.install_config(config):
            return
        self.nodes = {node.node_key: node for node in nodes}
        self.subscription_hash = content_hash
        await self.xray.restart()
        logger.info(
            "subscription_sync_success nodes=%d excluded=%d changed=true ignored=%s invalid=%d",
            len(nodes),
            len(excluded_nodes),
            parsed.ignored_protocols,
            parsed.invalid_count,
        )

    async def _probe_loop(self) -> None:
        await run_fixed_interval(
            self.probes.run_once, self.settings.probe_interval, self.stop_event
        )

    async def _subscription_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                await asyncio.wait_for(
                    self.stop_event.wait(), self.settings.subscription_sync_interval
                )
            except TimeoutError:
                await self.sync_subscription()

    async def health_status(self) -> dict[str, object]:
        nodes = await self.repository.list_nodes(active_only=True)
        return {
            "status": "ok",
            "xray": "running"
            if self.xray.process and self.xray.process.returncode is None
            else "stopped",
            "subscription_last_success": self.last_subscription_success.isoformat()
            if self.last_subscription_success
            else None,
            "active_nodes": len(nodes),
            "up_nodes": sum(node.current_status == "up" for node in nodes),
            "down_nodes": sum(node.current_status == "down" for node in nodes),
        }

    async def close(self) -> None:
        self.stop_event.set()
        await self.xray.stop()
        await self.health.close()
        await self.fetcher.close()
        await self.push.close()
        await self.management.close()
        await self.database.close()


async def async_main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    configure_logging(settings.log_level)
    app = Application(settings)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, app.stop_event.set)
    try:
        await app.start()
    finally:
        await app.close()


def run() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    run()
