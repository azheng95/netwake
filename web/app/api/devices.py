import sqlite3
from typing import Any

from fastapi import APIRouter, Header, HTTPException

from ..auth import require_admin
from ..repository import create_device, delete_device, list_devices, log_event, update_device
from ..schemas import DeviceCreate, DeviceUpdate

router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.get("")
def get_devices(x_admin_token: str | None = Header(default=None)) -> list[dict[str, Any]]:
    require_admin(x_admin_token)
    return list_devices()


@router.post("", status_code=201)
def add_device(
    device: DeviceCreate,
    x_admin_token: str | None = Header(default=None),
) -> dict[str, Any]:
    require_admin(x_admin_token)
    try:
        result = create_device(device.model_dump())
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="该 MAC 地址已经存在") from exc
    log_event("device", f"新增设备 {result['mac']}", {"mac": result["mac"]})
    return result


@router.patch("/{device_id}")
def edit_device(
    device_id: int,
    device: DeviceUpdate,
    x_admin_token: str | None = Header(default=None),
) -> dict[str, Any]:
    require_admin(x_admin_token)
    values = device.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")
    result = update_device(device_id, values)
    if result is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    log_event("device", f"更新设备 {result['mac']}", {"id": device_id, "fields": list(values)})
    return result


@router.delete("/{device_id}", status_code=204)
def remove_device(
    device_id: int,
    x_admin_token: str | None = Header(default=None),
) -> None:
    require_admin(x_admin_token)
    row = delete_device(device_id)
    if not row:
        raise HTTPException(status_code=404, detail="设备不存在")
    log_event("device", f"删除设备 {row['mac']}", {"id": device_id})
