import ipaddress
from pydantic import BaseModel, Field, field_validator


PRIVATE_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
)


def is_local_ipv4(address: ipaddress.IPv4Address) -> bool:
    return any(address in network for network in PRIVATE_NETWORKS)


class ScanRequest(BaseModel):
    cidr: str = Field(default="192.168.0.0/24", max_length=43)
    interface: str | None = Field(default=None, max_length=32)
    timeout: float = Field(default=2.0, ge=0.2, le=10.0)


class WakeRequest(BaseModel):
    mac: str = Field(min_length=12, max_length=17)
    broadcast: str | None = Field(default=None, max_length=15)
    port: int = Field(default=9, ge=1, le=65535)

    @field_validator("mac")
    @classmethod
    def validate_mac(cls, value: str) -> str:
        from .security import normalize_mac

        return normalize_mac(value)[0]

    @field_validator("broadcast")
    @classmethod
    def validate_broadcast(cls, value: str | None) -> str | None:
        if value is None or value == "255.255.255.255":
            return value
        try:
            address = ipaddress.ip_address(value)
        except ValueError as exc:
            raise ValueError("Invalid broadcast address") from exc
        if not isinstance(address, ipaddress.IPv4Address) or not is_local_ipv4(address):
            raise ValueError("WoL broadcast must be an IPv4 private or link-local address")
        return str(address)


class ProbeRequest(BaseModel):
    ip: str
    ports: list[int] = Field(default_factory=lambda: [80, 443, 22, 3389, 445], max_length=12)
    timeout: float = Field(default=0.7, ge=0.1, le=5.0)

    @field_validator("ip")
    @classmethod
    def validate_ip(cls, value: str) -> str:
        try:
            address = ipaddress.ip_address(value)
        except ValueError as exc:
            raise ValueError("Invalid IP address") from exc
        if not isinstance(address, ipaddress.IPv4Address) or not is_local_ipv4(address):
            raise ValueError("Only private or link-local IPv4 targets are allowed")
        return str(address)

    @field_validator("ports")
    @classmethod
    def validate_ports(cls, value: list[int]) -> list[int]:
        if any(port < 1 or port > 65535 for port in value):
            raise ValueError("Ports must be between 1 and 65535")
        return list(dict.fromkeys(value))
