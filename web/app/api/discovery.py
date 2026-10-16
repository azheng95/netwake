from typing import Any

from fastapi import APIRouter, Header

from ..auth import require_admin
from ..integrations import agent_request
from ..schemas import ScanRequest
from ..services.discovery import scan

router = APIRouter(prefix="/api/discovery", tags=["discovery"])


@router.get("/interfaces")
def get_interfaces(
    x_admin_token: str | None = Header(default=None),
) -> dict[str, Any]:
    require_admin(x_admin_token)
    return agent_request("GET", "/v1/interfaces")


@router.post("/scan")
def start_scan(
    request: ScanRequest,
    x_admin_token: str | None = Header(default=None),
) -> dict[str, Any]:
    require_admin(x_admin_token)
    return scan(request)
