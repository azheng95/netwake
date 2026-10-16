from fastapi import APIRouter, Header

from ..auth import require_admin
from ..services.wol import probe, wake

router = APIRouter(prefix="/api/devices", tags=["wol"])


@router.post("/{device_id}/wake")
def wake_device(
    device_id: int,
    x_admin_token: str | None = Header(default=None),
) -> dict:
    require_admin(x_admin_token)
    return wake(device_id)


@router.post("/{device_id}/probe")
def probe_device(
    device_id: int,
    x_admin_token: str | None = Header(default=None),
) -> dict:
    require_admin(x_admin_token)
    return probe(device_id)
