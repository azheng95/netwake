import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .config import DB_PATH


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize() -> None:
    with db() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL DEFAULT '',
                mac TEXT NOT NULL UNIQUE,
                ip TEXT,
                hostname TEXT,
                broadcast TEXT,
                wol_status TEXT NOT NULL DEFAULT 'unknown',
                notes TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT 'manual',
                is_online INTEGER NOT NULL DEFAULT 0,
                last_seen_at TEXT,
                last_wake_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_devices_ip ON devices(ip);
            CREATE TABLE IF NOT EXISTS activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                message TEXT NOT NULL,
                payload TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            INSERT OR IGNORE INTO app_settings(key, value)
            VALUES ('admin_token_saved', 'false');
            """
        )


def admin_token_saved() -> bool:
    with db() as connection:
        row = connection.execute(
            "SELECT value FROM app_settings WHERE key = 'admin_token_saved'"
        ).fetchone()
    return bool(row and row["value"] == "true")


def mark_admin_token_saved() -> None:
    with db() as connection:
        connection.execute(
            "UPDATE app_settings SET value = 'true' WHERE key = 'admin_token_saved'"
        )
