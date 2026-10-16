from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from .api import devices, discovery, system, wol
from .auth import validate_admin_configuration
from .config import STATIC_DIR
from .database import initialize

app = FastAPI(
    title="NetWake",
    version="1.0.0",
    openapi_url=None,
    docs_url=None,
    redoc_url=None,
)
app.include_router(system.router)
app.include_router(devices.router)
app.include_router(discovery.router)
app.include_router(wol.router)


@app.on_event("startup")
def startup() -> None:
    validate_admin_configuration()
    initialize()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/openapi.json")
@app.get("/docs")
@app.get("/redoc")
def disabled_api_documentation() -> None:
    raise HTTPException(status_code=404, detail="Not found")


@app.get("/docs/{path:path}")
@app.get("/redoc/{path:path}")
def disabled_api_documentation_assets(path: str) -> None:
    raise HTTPException(status_code=404, detail="Not found")


@app.get("/{path:path}")
def static_files(path: str) -> FileResponse:
    candidate = (STATIC_DIR / path).resolve()
    if candidate.parent == STATIC_DIR.resolve() and candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(STATIC_DIR / "index.html")
