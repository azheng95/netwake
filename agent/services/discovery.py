import ipaddress
import socket
import struct
import time
from types import SimpleNamespace

from fastapi import HTTPException

from ..schemas import PRIVATE_NETWORKS
from ..security import normalize_mac


def _scapy():
    try:
        from scapy.all import ARP, Ether, IP, UDP, conf, get_if_addr, get_if_list, sr, srp
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=f"Scapy network backend unavailable: {exc}") from exc
    return SimpleNamespace(
        ARP=ARP,
        Ether=Ether,
        IP=IP,
        UDP=UDP,
        conf=conf,
        get_if_addr=get_if_addr,
        get_if_list=get_if_list,
        sr=sr,
        srp=srp,
    )


def list_interfaces() -> list[dict[str, str | None]]:
    scapy = _scapy()
    result = []
    for name in scapy.get_if_list():
        try:
            address = scapy.get_if_addr(name)
        except Exception:
            address = None
        cidr = None
        try:
            ip = ipaddress.ip_address(address)
            netmask = _linux_interface_netmask(name)
            if isinstance(ip, ipaddress.IPv4Address) and netmask:
                network = ipaddress.ip_network(f"{ip}/{netmask}", strict=False)
                if (
                    network.num_addresses >= 4
                    and network.num_addresses <= 4096
                    and any(network.subnet_of(allowed) for allowed in PRIVATE_NETWORKS)
                ):
                    cidr = str(network)
        except (TypeError, ValueError, OSError):
            pass
        result.append({"name": name, "ipv4": address, "cidr": cidr})
    return result


def _linux_interface_netmask(name: str) -> str | None:
    if not name or len(name.encode()) > 15 or "\x00" in name:
        return None
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            response = sock.fileno()
            import fcntl

            result = fcntl.ioctl(response, 0x891B, struct.pack("256s", name.encode()))
        return socket.inet_ntoa(result[20:24])
    except (ImportError, OSError, ValueError):
        return None


def _resolve_netbios_hostnames(addresses: list[str], interface: str) -> dict[str, str]:
    if not addresses:
        return {}
    scapy = _scapy()
    try:
        from scapy.layers.netbios import NBNSHeader, NBNSNodeStatusRequest, NBNSNodeStatusResponse
    except ImportError:
        return {}
    if not all(hasattr(scapy, name) for name in ("IP", "UDP", "sr")):
        return {}
    names_by_ip = {}
    requests = [
        scapy.IP(dst=address)
        / scapy.UDP(sport=137, dport=137)
        / NBNSHeader(NAME_TRN_ID=(index + 1) % 65536, QDCOUNT=1)
        / NBNSNodeStatusRequest()
        for index, address in enumerate(addresses)
    ]
    try:
        answered, _ = scapy.sr(requests, timeout=0.4, iface=interface, verbose=False)
    except Exception:
        return {}
    for request, response in answered:
        try:
            address = request[scapy.IP].dst
            status = response.getlayer(NBNSNodeStatusResponse)
            if status is None:
                continue
            names = status.NODE_NAME or []
            workstation = next(
                (entry for entry in names if int(entry.SUFFIX) == 0),
                names[0] if names else None,
            )
            if workstation:
                hostname = workstation.NETBIOS_NAME.decode("ascii", errors="ignore").strip()
                if hostname and hostname not in {"*", "<00>"}:
                    names_by_ip[address] = hostname[:253]
        except (AttributeError, IndexError, KeyError, TypeError, ValueError):
            continue
    return names_by_ip


def scan_network(cidr: str, requested_interface: str | None, default_interface: str, timeout: float) -> dict:
    try:
        network = ipaddress.ip_network(cidr, strict=False)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid CIDR: {exc}") from exc
    if network.version != 4:
        raise HTTPException(status_code=400, detail="Only IPv4 networks are supported")
    if network.num_addresses > 4096:
        raise HTTPException(status_code=400, detail="Scan range is limited to 4096 addresses")
    if not any(network.subnet_of(allowed) for allowed in PRIVATE_NETWORKS):
        raise HTTPException(status_code=400, detail="Only private or link-local networks can be scanned")

    scapy = _scapy()
    interface = (requested_interface or default_interface or str(scapy.conf.iface)).strip()
    if interface not in scapy.get_if_list():
        raise HTTPException(status_code=400, detail=f"Unknown network interface: {interface}")
    try:
        interface_ip = ipaddress.ip_address(scapy.get_if_addr(interface))
    except (TypeError, ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=f"Interface {interface} has no usable IPv4 address") from exc
    if not isinstance(interface_ip, ipaddress.IPv4Address) or interface_ip not in network:
        raise HTTPException(status_code=400, detail=f"Scan range {network} is not on interface {interface}")
    for endpoint in {network.network_address, network.broadcast_address}:
        route_interface, _, gateway = scapy.conf.route.route(str(endpoint))
        if str(route_interface) != interface or gateway not in {"0.0.0.0", "0", None}:
            raise HTTPException(
                status_code=400,
                detail=f"Scan range {network} is not directly connected to interface {interface}",
            )

    started = time.monotonic()
    try:
        answered, _ = scapy.srp(
            scapy.Ether(dst="ff:ff:ff:ff:ff:ff") / scapy.ARP(pdst=str(network)),
            timeout=timeout,
            iface=interface,
            verbose=False,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"ARP scan failed on {interface}: {exc}") from exc

    devices_by_mac = {}
    for _, received in answered:
        try:
            address = ipaddress.ip_address(received.psrc)
            if not isinstance(address, ipaddress.IPv4Address) or address not in network:
                continue
            mac, _ = normalize_mac(received.hwsrc)
        except (AttributeError, ValueError, HTTPException):
            continue
        devices_by_mac[mac] = {
            "ip": str(address),
            "mac": mac,
            "hostname": None,
            "interface": interface,
            "source": "arp",
        }

    devices = sorted(devices_by_mac.values(), key=lambda item: ipaddress.ip_address(item["ip"]))
    hostnames = _resolve_netbios_hostnames([device["ip"] for device in devices], interface)
    for device in devices:
        device["hostname"] = hostnames.get(device["ip"])
    return {
        "cidr": str(network),
        "interface": interface,
        "duration_ms": round((time.monotonic() - started) * 1000),
        "devices": devices,
    }
