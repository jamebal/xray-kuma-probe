import sqlite3
from pathlib import Path


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.connection: sqlite3.Connection | None = None

    async def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);
            INSERT INTO schema_version(version)
                SELECT 1 WHERE NOT EXISTS (SELECT 1 FROM schema_version);
            CREATE TABLE IF NOT EXISTS nodes (
                id INTEGER PRIMARY KEY, node_key TEXT UNIQUE NOT NULL, display_name TEXT NOT NULL,
                protocol TEXT NOT NULL, fingerprint TEXT NOT NULL,
                socks_port INTEGER UNIQUE NOT NULL,
                kuma_monitor_id INTEGER, kuma_push_token TEXT, first_seen_at REAL NOT NULL,
                last_seen_at REAL NOT NULL, removed_at REAL, enabled INTEGER NOT NULL DEFAULT 1,
                consecutive_success INTEGER NOT NULL DEFAULT 0,
                consecutive_failure INTEGER NOT NULL DEFAULT 0,
                current_status TEXT NOT NULL DEFAULT 'up'
            );
            CREATE TABLE IF NOT EXISTS config_state (
                id INTEGER PRIMARY KEY CHECK(id=1), subscription_hash TEXT, xray_config_hash TEXT,
                last_sync_at REAL, subscription_last_success REAL, kuma_group_monitor_id INTEGER
            );
            INSERT OR IGNORE INTO config_state(id) VALUES(1);
        """)
        config_columns = {
            row["name"] for row in self.connection.execute("PRAGMA table_info(config_state)")
        }
        if "kuma_group_monitor_id" not in config_columns:
            self.connection.execute(
                "ALTER TABLE config_state ADD COLUMN kuma_group_monitor_id INTEGER"
            )
            self.connection.execute("UPDATE schema_version SET version=2")
        self.connection.commit()

    async def close(self) -> None:
        if self.connection:
            self.connection.close()
            self.connection = None

    def require(self) -> sqlite3.Connection:
        if self.connection is None:
            raise RuntimeError("数据库尚未初始化")
        return self.connection
