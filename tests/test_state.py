import sqlite3
from pathlib import Path

import pytest

from app.state.database import Database
from app.state.repository import NodeRepository
from app.subscription.parser import parse_subscription

from .test_subscription import VLESS


@pytest.mark.asyncio
async def test_port_is_stable_across_restart_and_reappearance(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    node = parse_subscription(VLESS).nodes[0]
    db = Database(path)
    await db.initialize()
    repo = NodeRepository(db, 20000, 20002)
    record = await repo.upsert_node(node)
    await repo.mark_missing(set(), 0)
    restored = await repo.upsert_node(node)
    await db.close()

    db2 = Database(path)
    await db2.initialize()
    record2 = await NodeRepository(db2, 20000, 20002).upsert_node(node)
    assert record.socks_port == restored.socks_port == record2.socks_port
    assert restored.removed_at is None
    await db2.close()


@pytest.mark.asyncio
async def test_probe_thresholds_transition_state(tmp_path: Path) -> None:
    db = Database(tmp_path / "state.db")
    await db.initialize()
    repo = NodeRepository(db, 20000, 20010)
    record = await repo.upsert_node(parse_subscription(VLESS).nodes[0])
    assert await repo.record_probe(record.node_key, False, 2, 1) == "up"
    assert await repo.record_probe(record.node_key, False, 2, 1) == "down"
    assert await repo.record_probe(record.node_key, True, 2, 1) == "up"
    await db.close()


@pytest.mark.asyncio
async def test_kuma_group_id_persists_across_restart(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    db = Database(path)
    await db.initialize()
    repo = NodeRepository(db, 20000, 20010)
    await repo.set_kuma_group_id(42)
    await db.close()

    reopened = Database(path)
    await reopened.initialize()
    assert await NodeRepository(reopened, 20000, 20010).get_kuma_group_id() == 42
    await reopened.close()


@pytest.mark.asyncio
async def test_existing_config_state_is_migrated_for_group_id(tmp_path: Path) -> None:
    path = tmp_path / "old.db"
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE schema_version (version INTEGER NOT NULL);
        INSERT INTO schema_version VALUES (1);
        CREATE TABLE config_state (
            id INTEGER PRIMARY KEY, subscription_hash TEXT, xray_config_hash TEXT,
            last_sync_at REAL, subscription_last_success REAL
        );
        INSERT INTO config_state(id) VALUES(1);
    """)
    connection.close()

    database = Database(path)
    await database.initialize()
    await NodeRepository(database, 20000, 20010).set_kuma_group_id(42)
    assert await NodeRepository(database, 20000, 20010).get_kuma_group_id() == 42
    await database.close()
