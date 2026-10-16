import socket

from fastapi import HTTPException

from ..security import normalize_mac


def send_magic_packet(mac_address: str, broadcast: str | None, port: int) -> dict:
    mac, mac_bytes = normalize_mac(mac_address)
    destination = broadcast or "255.255.255.255"
    packet = b"\xff" * 6 + mac_bytes * 16
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sent = sock.sendto(packet, (destination, port))
    except OSError as exc:
        raise HTTPException(status_code=502, detail=f"Magic packet failed: {exc}") from exc

    return {
        "packet_sent": sent == len(packet),
        "bytes_sent": sent,
        "mac": mac,
        "broadcast": destination,
        "port": port,
    }
