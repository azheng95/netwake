from datetime import datetime, timezone

from fastapi import HTTPException

from agent.schemas import ProbeRequest, ScanRequest, WakeRequest
from agent.services.discovery import list_interfaces, scan_network
from agent.services.probe import probe_host
from agent.services.wol import send_magic_packet

from .config import AGENT_NAME, APP_VERSION, SCAN_INTERFACE


def agent_request(method: str, path: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    if method == "GET" and path == "/healthz":
        return {
            "ok": True,
            "name": AGENT_NAME,
            "version": APP_VERSION,
            "interface": SCAN_INTERFACE or None,
            "capabilities": ["arp_scan", "wake_on_lan", "tcp_probe", "icmp_probe"],
            "time": datetime.now(timezone.utc).isoformat(),
        }
    if method == "GET" and path == "/v1/interfaces":
        return {"interfaces": list_interfaces()}
    if method == "POST" and path == "/v1/discovery/scan":
        request = ScanRequest(**payload)
        return scan_network(
            request.cidr,
            request.interface,
            SCAN_INTERFACE,
            request.timeout,
        )
    if method == "POST" and path == "/v1/wol":
        request = WakeRequest(**payload)
        return send_magic_packet(
            request.mac,
            request.broadcast,
            request.port,
        )
    if method == "POST" and path == "/v1/probe":
        request = ProbeRequest(**payload)
        return probe_host(
            request.ip,
            request.ports,
            request.timeout,
        )
    raise HTTPException(status_code=404, detail="Unknown LAN operation")
