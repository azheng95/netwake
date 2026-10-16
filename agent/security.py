import hmac
import re

from fastapi import HTTPException


def normalize_mac(value: str) -> tuple[str, bytes]:
    value = value.strip()
    if re.fullmatch(r"[0-9a-fA-F]{12}", value):
        compact = value
    elif re.fullmatch(r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}", value):
        compact = value.replace(":", "")
    elif re.fullmatch(r"(?:[0-9a-fA-F]{2}-){5}[0-9a-fA-F]{2}", value):
        compact = value.replace("-", "")
    else:
        raise HTTPException(status_code=400, detail="Invalid MAC address")
    raw = bytes.fromhex(compact)
    if raw == b"\x00" * 6 or raw[0] & 1:
        raise HTTPException(status_code=400, detail="MAC must be a unicast address")
    return ":".join(compact[i : i + 2] for i in range(0, 12, 2)).upper(), raw


def check_agent_token(token: str | None, expected: str) -> None:
    if not token or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Invalid agent token")
