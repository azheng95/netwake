import ipaddress
import sqlite3
from typing import Any

from fastapi import HTTPException

from ..database import db
from ..integrations import agent_request
from ..repository import log_event, utc_now
from ..schemas import ScanRequest, normalize_mac


def merge_scan(result: dict[str, Any]) -> tuple[int, int]:
    try:
        network = ipaddress.ip_network(result["cidr"], strict=False)
        if network.version != 4 or network.num_addresses > 4096:
            raise ValueError("Invalid scan range")
        if not any(
            network.subnet_of(allowed)
            for allowed in (
                ipaddress.ip_network("10.0.0.0/8"),
                ipaddress.ip_network("172.16.0.0/12"),
                ipaddress.ip_network("192.168.0.0/16"),
                ipaddress.ip_network("169.254.0.0/16"),
            )
        ):
            raise ValueError("Scan range is outside local networks")
        devices = result["devices"]
        if not isinstance(devices, list):
            raise ValueError("Invalid device list")
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Agent returned an invalid scan result") from exc

    sanitized = []
    for item in devices:
        try:
            address = ipaddress.ip_address(item["ip"])
            mac = normalize_mac(item["mac"])
            if not isinstance(address, ipaddress.IPv4Address) or address not in network:
                continue
            sanitized.append(
                {
                    "ip": str(address),
                    "mac": mac,
                    "hostname": str(item["hostname"])[:253] if item.get("hostname") else None,
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    result = {**result, "devices": sanitized}

    timestamp = utc_now()
    broadcast = str(network.broadcast_address)
    added = updated = 0
    with db() as connection:
        known_devices = connection.execute("SELECT id, ip FROM devices WHERE ip IS NOT NULL").fetchall()
        for known in known_devices:
            try:
                belongs_to_scan = ipaddress.ip_address(known["ip"]) in network
            except ValueError:
                belongs_to_scan = False
            if belongs_to_scan:
                connection.execute(
                    "UPDATE devices SET is_online = 0, updated_at = ? WHERE id = ?",
                    (timestamp, known["id"]),
                )
        for discovered in sanitized:
            existing = connection.execute(
                "SELECT id, name, hostname FROM devices WHERE mac = ?", (discovered["mac"],)
            ).fetchone()
            if existing:
                name = existing["name"]
                if discovered["hostname"] and name in {discovered["mac"], existing["hostname"]}:
                    name = discovered["hostname"]
                connection.execute(
                    """
                    UPDATE devices
                    SET name = ?, ip = ?, hostname = COALESCE(?, hostname), broadcast = ?, source = 'arp', is_online = 1,
                        last_seen_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        name,
                        discovered["ip"],
                        discovered["hostname"],
                        broadcast,
                        timestamp,
                        timestamp,
                        existing["id"],
                    ),
                )
                updated += 1
            else:
                try:
                    connection.execute(
                        """
                        INSERT INTO devices(name, mac, ip, hostname, broadcast, wol_status, notes,
                                             source, is_online, last_seen_at, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, 'unknown', '', 'arp', 1, ?, ?, ?)
                        """,
                        (
                            discovered["hostname"] or discovered["mac"],
                            discovered["mac"],
                            discovered["ip"],
                            discovered["hostname"],
                            broadcast,
                            timestamp,
                            timestamp,
                            timestamp,
                        ),
                    )
                except sqlite3.IntegrityError:
                    continue
                added += 1
    return added, updated


def scan(request: ScanRequest) -> dict[str, Any]:
    result = agent_request(
        "POST",
        "/v1/discovery/scan",
        {"cidr": request.cidr, "interface": request.interface},
    )
    added, updated = merge_scan(result)
    log_event(
        "scan",
        f"扫描完成，发现 {len(result['devices'])} 台在线设备",
        {"cidr": result["cidr"], "added": added, "updated": updated},
    )
    return {**result, "added": added, "updated": updated}
