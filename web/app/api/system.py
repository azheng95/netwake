from typing import Any

from fastapi import APIRouter, Header, HTTPException

from ..auth import require_admin
from ..config import ALLOW_INITIAL_TOKEN_ENDPOINT, APP_TOKEN, APP_VERSION, DEFAULT_CIDR
from ..database import admin_token_saved, mark_admin_token_saved
from ..integrations import agent_request
from ..repository import list_activity, utc_now

router = APIRouter(tags=["system"])


@router.get("/healthz")
def healthz() -> dict[str, Any]:
    return {"ok": True, "version": APP_VERSION, "time": utc_now()}


@router.get("/api/config")
def config() -> dict[str, Any]:
    return {"version": APP_VERSION, "auth_enabled": True, "default_cidr": DEFAULT_CIDR}


@router.get("/api/setup/initial-token")
def initial_token() -> dict[str, str]:
    if not ALLOW_INITIAL_TOKEN_ENDPOINT or admin_token_saved():
        raise HTTPException(status_code=404, detail="Initial token setup is complete")
    return {"token": APP_TOKEN}


@router.post("/api/setup/token-saved", status_code=204)
def token_saved(x_admin_token: str | None = Header(default=None)) -> None:
    require_admin(x_admin_token)
    mark_admin_token_saved()


@router.get("/api/agent/status")
def agent_status(x_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    require_admin(x_admin_token)
    return agent_request("GET", "/healthz")


@router.get("/api/activity")
def activity(
    limit: int = 40,
    x_admin_token: str | None = Header(default=None),
) -> list[dict[str, Any]]:
    require_admin(x_admin_token)
    return list_activity(max(1, min(limit, 200)))
