import ipaddress
import re

from pydantic import BaseModel, Field, field_validator, model_validator

from .config import DEFAULT_CIDR


PRIVATE_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
)


def normalize_mac(value: str) -> str:
    value = value.strip()
    if re.fullmatch(r"[0-9a-fA-F]{12}", value):
        compact = value
    elif re.fullmatch(r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}", value):
        compact = value.replace(":", "")
    elif re.fullmatch(r"(?:[0-9a-fA-F]{2}-){5}[0-9a-fA-F]{2}", value):
        compact = value.replace("-", "")
    else:
        raise ValueError("MAC 地址格式不正确")
    raw = bytes.fromhex(compact)
    if raw == b"\x00" * 6 or raw[0] & 1:
        raise ValueError("MAC 地址必须是单播地址")
    return ":".join(compact[i : i + 2] for i in range(0, 12, 2)).upper()


def local_ipv4(value: str | None, label: str) -> str | None:
    if value is None or value == "":
        return None
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise ValueError(f"{label}必须是有效 IPv4 地址") from exc
    if not isinstance(address, ipaddress.IPv4Address) or not any(
        address in network for network in PRIVATE_NETWORKS
    ):
        raise ValueError(f"{label}仅支持私网或链路本地 IPv4 地址")
    return str(address)


class DeviceCreate(BaseModel):
    name: str = Field(default="", max_length=120)
    mac: str = Field(min_length=12, max_length=17)
    ip: str | None = None
    hostname: str | None = Field(default=None, max_length=253)
    broadcast: str | None = None
    wol_status: str = "unknown"
    notes: str = Field(default="", max_length=2000)

    @field_validator("mac")
    @classmethod
    def validate_mac(cls, value: str) -> str:
        return normalize_mac(value)

    @field_validator("ip")
    @classmethod
    def validate_ip(cls, value: str | None) -> str | None:
        return local_ipv4(value, "IP 地址")

    @field_validator("broadcast")
    @classmethod
    def validate_broadcast(cls, value: str | None) -> str | None:
        if value == "255.255.255.255":
            return value
        return local_ipv4(value, "广播地址")

    @field_validator("wol_status")
    @classmethod
    def validate_wol_status(cls, value: str) -> str:
        if value not in {"unknown", "verified", "unsupported"}:
            raise ValueError("WoL 状态不合法")
        return value


class DeviceUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    ip: str | None = None
    hostname: str | None = Field(default=None, max_length=253)
    broadcast: str | None = None
    wol_status: str | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="before")
    @classmethod
    def reject_null_required_fields(cls, values):
        if isinstance(values, dict):
            for field in ("name", "wol_status", "notes"):
                if field in values and values[field] is None:
                    raise ValueError(f"{field} 不能设为 null")
        return values

    @field_validator("ip")
    @classmethod
    def validate_ip(cls, value: str | None) -> str | None:
        return local_ipv4(value, "IP 地址")

    @field_validator("broadcast")
    @classmethod
    def validate_broadcast(cls, value: str | None) -> str | None:
        if value == "255.255.255.255":
            return value
        return local_ipv4(value, "广播地址")

    @field_validator("wol_status")
    @classmethod
    def validate_wol_status(cls, value: str | None) -> str | None:
        if value is not None and value not in {"unknown", "verified", "unsupported"}:
            raise ValueError("WoL 状态不合法")
        return value


class ScanRequest(BaseModel):
    cidr: str = Field(default=DEFAULT_CIDR, max_length=43)
    interface: str | None = Field(default=None, max_length=32)

    @field_validator("cidr")
    @classmethod
    def validate_cidr(cls, value: str) -> str:
        try:
            network = ipaddress.ip_network(value, strict=False)
        except ValueError as exc:
            raise ValueError("扫描网段格式不正确") from exc
        if network.version != 4 or network.num_addresses > 4096:
            raise ValueError("仅支持最多 4096 个地址的 IPv4 扫描网段")
        if not any(network.subnet_of(allowed) for allowed in PRIVATE_NETWORKS):
            raise ValueError("仅允许扫描私网或链路本地网段")
        return str(network)
