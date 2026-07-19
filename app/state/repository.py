import sqlite3
import time
from dataclasses import dataclass

from app.subscription.models import ProxyNode

from .database import Database


@dataclass(frozen=True, slots=True)
class NodeRecord:
    node_key: str
    display_name: str
    protocol: str
    fingerprint: str
    socks_port: int
    kuma_monitor_id: int | None
    kuma_push_token: str | None
    first_seen_at: float
    last_seen_at: float
    removed_at: float | None
    enabled: bool
    consecutive_success: int
    consecutive_failure: int
    current_status: str


class NodeRepository:
    def __init__(self, database: Database, port_start: int, port_end: int) -> None:
        self.db = database
        self.port_start = port_start
        self.port_end = port_end

    def _row(self, row: sqlite3.Row) -> NodeRecord:
        values = dict(row)
        values.pop("id", None)
        values["enabled"] = bool(values["enabled"])
        return NodeRecord(**values)

    async def upsert_node(self, node: ProxyNode) -> NodeRecord:
        conn, now = self.db.require(), time.time()
        existing = conn.execute("SELECT * FROM nodes WHERE node_key=?", (node.node_key,)).fetchone()
        if existing:
            conn.execute(
                "UPDATE nodes SET display_name=?,protocol=?,fingerprint=?,last_seen_at=?,"
                "removed_at=NULL,enabled=1 WHERE node_key=?",
                (node.display_name, node.protocol, node.fingerprint, now, node.node_key),
            )
        else:
            ports = {row[0] for row in conn.execute("SELECT socks_port FROM nodes")}
            port = next(
                (
                    value
                    for value in range(self.port_start, self.port_end + 1)
                    if value not in ports
                ),
                None,
            )
            if port is None:
                raise RuntimeError("SOCKS 端口池已耗尽")
            conn.execute(
                "INSERT INTO nodes(node_key,display_name,protocol,fingerprint,socks_port,"
                "first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?)",
                (node.node_key, node.display_name, node.protocol, node.fingerprint, port, now, now),
            )
        conn.commit()
        return self._row(
            conn.execute("SELECT * FROM nodes WHERE node_key=?", (node.node_key,)).fetchone()
        )

    async def list_nodes(self, active_only: bool = False) -> list[NodeRecord]:
        sql = (
            "SELECT * FROM nodes"
            + (" WHERE enabled=1 AND removed_at IS NULL" if active_only else "")
            + " ORDER BY id"
        )
        return [self._row(row) for row in self.db.require().execute(sql)]

    async def mark_missing(self, active_keys: set[str], grace_period: int) -> None:
        conn, now = self.db.require(), time.time()
        for row in conn.execute("SELECT node_key,removed_at FROM nodes WHERE enabled=1"):
            if row["node_key"] not in active_keys:
                removed = row["removed_at"] or now
                enabled = int(now - removed < grace_period)
                conn.execute(
                    "UPDATE nodes SET removed_at=?,enabled=? WHERE node_key=?",
                    (removed, enabled, row["node_key"]),
                )
        conn.commit()

    async def disable_nodes(self, node_keys: set[str]) -> None:
        if not node_keys:
            return
        conn, now = self.db.require(), time.time()
        keys = sorted(node_keys)
        placeholders = ",".join("?" for _ in keys)
        conn.execute(
            f"UPDATE nodes SET removed_at=?,enabled=0 "
            f"WHERE node_key IN ({placeholders}) AND enabled=1",
            (now, *keys),
        )
        conn.commit()

    async def set_kuma(self, node_key: str, monitor_id: int, token: str) -> None:
        conn = self.db.require()
        conn.execute(
            "UPDATE nodes SET kuma_monitor_id=?,kuma_push_token=? WHERE node_key=?",
            (monitor_id, token, node_key),
        )
        conn.commit()

    async def get_kuma_group_id(self) -> int | None:
        row = self.db.require().execute(
            "SELECT kuma_group_monitor_id FROM config_state WHERE id=1"
        ).fetchone()
        value = row["kuma_group_monitor_id"] if row else None
        return int(value) if value is not None else None

    async def set_kuma_group_id(self, monitor_id: int) -> None:
        conn = self.db.require()
        conn.execute(
            "UPDATE config_state SET kuma_group_monitor_id=? WHERE id=1", (monitor_id,)
        )
        conn.commit()

    async def record_probe(
        self, node_key: str, success: bool, failure_threshold: int, recovery_threshold: int
    ) -> str:
        conn = self.db.require()
        record = self._row(
            conn.execute("SELECT * FROM nodes WHERE node_key=?", (node_key,)).fetchone()
        )
        successes = record.consecutive_success + 1 if success else 0
        failures = 0 if success else record.consecutive_failure + 1
        status = record.current_status
        if not success and failures >= failure_threshold:
            status = "down"
        elif success and successes >= recovery_threshold:
            status = "up"
        conn.execute(
            "UPDATE nodes SET consecutive_success=?,consecutive_failure=?,"
            "current_status=? WHERE node_key=?",
            (successes, failures, status, node_key),
        )
        conn.commit()
        return status
