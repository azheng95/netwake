from fastapi import HTTPException

from ..integrations import agent_request
from ..repository import get_device, log_event, set_device_presence, update_device, utc_now


def wake(device_id: int) -> dict:
    row = get_device(device_id)
    if not row:
        raise HTTPException(status_code=404, detail="设备不存在")
    result = agent_request(
        "POST",
        "/v1/wol",
        {
            "mac": row["mac"],
            "broadcast": row["broadcast"] or "255.255.255.255",
            "port": 9,
        },
    )
    timestamp = utc_now()
    update_device(device_id, {"last_wake_at": timestamp})
    log_event("wake", f"已向 {row['mac']} 发送 WoL 包", {"id": device_id, **result})
    return {"device": dict(row), "result": result}


def probe(device_id: int) -> dict:
    row = get_device(device_id)
    if not row:
        raise HTTPException(status_code=404, detail="设备不存在")
    if not row["ip"]:
        raise HTTPException(status_code=400, detail="设备没有 IP 地址")
    result = agent_request("POST", "/v1/probe", {"ip": row["ip"]})
    timestamp = utc_now()
    set_device_presence(device_id, bool(result["online"]), timestamp if result["online"] else None)
    log_event("probe", f"探测 {row['ip']} {'在线' if result['online'] else '离线'}", result)
    return {"device_id": device_id, **result}
