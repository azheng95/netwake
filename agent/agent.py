import os
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Header, HTTPException

from .schemas import ProbeRequest, ScanRequest, WakeRequest
from .security import check_agent_token
from .services.discovery import list_interfaces, scan_network
from .services.probe import probe_host
from .services.wol import send_magic_packet


APP_VERSION = "1.0.1"
AGENT_TOKEN = os.getenv("AGENT_TOKEN", "")
AGENT_NAME = os.getenv("AGENT_NAME", "lanwake-agent")
DEFAULT_INTERFACE = os.getenv("SCAN_INTERFACE", "").strip()
PORT = int(os.getenv("PORT", "8081"))

app = FastAPI(
    title="LanWake Linux Agent",
    version=APP_VERSION,
    openapi_url=None,
    docs_url=None,
    redoc_url=None,
)


def require_agent_token(token: str | None) -> None:
    if not AGENT_TOKEN:
        raise HTTPException(status_code=503, detail="Agent token is not configured")
    check_agent_token(token, AGENT_TOKEN)


@app.on_event("startup")
def validate_configuration() -> None:
    if len(AGENT_TOKEN) < 32 or AGENT_TOKEN.lower().startswith("replace-with-"):
        raise RuntimeError("AGENT_TOKEN must be a unique random value with at least 32 characters")


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {
        "ok": True,
        "name": AGENT_NAME,
        "version": APP_VERSION,
        "interface": DEFAULT_INTERFACE or None,
        "capabilities": ["arp_scan", "wake_on_lan", "tcp_probe", "icmp_probe"],
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/openapi.json")
@app.get("/docs")
@app.get("/redoc")
def disabled_api_documentation() -> None:
    raise HTTPException(status_code=404, detail="Not found")


@app.get("/docs/{path:path}")
@app.get("/redoc/{path:path}")
def disabled_api_documentation_assets(path: str) -> None:
    raise HTTPException(status_code=404, detail="Not found")


@app.get("/v1/interfaces")
def interfaces(x_agent_token: str | None = Header(default=None)) -> dict[str, Any]:
    require_agent_token(x_agent_token)
    return {"interfaces": list_interfaces()}


@app.post("/v1/discovery/scan")
def scan(
    request: ScanRequest,
    x_agent_token: str | None = Header(default=None),
) -> dict[str, Any]:
    require_agent_token(x_agent_token)
    return scan_network(request.cidr, request.interface, DEFAULT_INTERFACE, request.timeout)


@app.post("/v1/wol")
def wake(
    request: WakeRequest,
    x_agent_token: str | None = Header(default=None),
) -> dict[str, Any]:
    require_agent_token(x_agent_token)
    return send_magic_packet(request.mac, request.broadcast, request.port)


@app.post("/v1/probe")
def probe(
    request: ProbeRequest,
    x_agent_token: str | None = Header(default=None),
) -> dict[str, Any]:
    require_agent_token(x_agent_token)
    return probe_host(request.ip, request.ports, request.timeout)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)
