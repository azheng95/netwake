import json
from datetime import datetime, timezone
from typing import Any

from .database import db


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def device_row(row) -> dict[str, Any]:
    result = dict(row)
    result["is_online"] = bool(result["is_online"])
    return result


def list_devices() -> list[dict[str, Any]]:
    with db() as connection:
        rows = connection.execute(
            "SELECT * FROM devices ORDER BY is_online DESC, name COLLATE NOCASE, ip"
        ).fetchall()
    return [device_row(row) for row in rows]


def create_device(device: dict[str, Any]) -> dict[str, Any]:
    timestamp = utc_now()
    with db() as connection:
        cursor = connection.execute(
            """
            INSERT INTO devices(name, mac, ip, hostname, broadcast, wol_status, notes, source,
                                 is_online, last_seen_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'manual', 0, NULL, ?, ?)
            """,
            (
                device["name"] or device["mac"],
                device["mac"],
                device.get("ip"),
                device.get("hostname"),
                device.get("broadcast"),
                device["wol_status"],
                device["notes"],
                timestamp,
                timestamp,
            ),
        )
        row = connection.execute("SELECT * FROM devices WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return device_row(row)


def set_device_presence(device_id: int, is_online: bool, last_seen_at: str | None = None) -> None:
    timestamp = utc_now()
    with db() as connection:
        connection.execute(
            """
            UPDATE devices
            SET is_online = ?, last_seen_at = COALESCE(?, last_seen_at), updated_at = ?
            WHERE id = ?
            """,
            (1 if is_online else 0, last_seen_at, timestamp, device_id),
        )


def get_device(device_id: int):
    with db() as connection:
        return connection.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()


def update_device(device_id: int, values: dict[str, Any]) -> dict[str, Any] | None:
    allowed_fields = {
        "name",
        "ip",
        "hostname",
        "broadcast",
        "wol_status",
        "notes",
        "source",
        "is_online",
        "last_seen_at",
        "last_wake_at",
    }
    if not values or set(values) - allowed_fields:
        raise ValueError("Invalid device update fields")
    values = {**values, "updated_at": utc_now()}
    assignments = ", ".join(f"{key} = ?" for key in values)
    with db() as connection:
        cursor = connection.execute(
            f"UPDATE devices SET {assignments} WHERE id = ?",
            (*values.values(), device_id),
        )
        if cursor.rowcount == 0:
            return None
        row = connection.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()
    return device_row(row)


def delete_device(device_id: int) -> dict[str, Any] | None:
    with db() as connection:
        row = connection.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()
        if row:
            connection.execute("DELETE FROM devices WHERE id = ?", (device_id,))
    return device_row(row) if row else None


def log_event(kind: str, message: str, payload: dict[str, Any] | None = None) -> None:
    with db() as connection:
        connection.execute(
            "INSERT INTO activity(kind, message, payload, created_at) VALUES (?, ?, ?, ?)",
            (kind, message, json.dumps(payload or {}, ensure_ascii=False), utc_now()),
        )


def list_activity(limit: int) -> list[dict[str, Any]]:
    with db() as connection:
        rows = connection.execute(
            "SELECT * FROM activity ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]
