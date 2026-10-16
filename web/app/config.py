import os
from pathlib import Path


APP_VERSION = "1.0.1"
DB_PATH = os.getenv("DB_PATH", "/data/netwake.db")
APP_TOKEN = os.getenv("APP_TOKEN", "")
AGENT_NAME = os.getenv("AGENT_NAME", "netwake-agent")
SCAN_INTERFACE = os.getenv("SCAN_INTERFACE", "").strip()
DEFAULT_CIDR = os.getenv("DEFAULT_CIDR", "192.168.0.0/24")
ALLOW_INITIAL_TOKEN_ENDPOINT = os.getenv("ALLOW_INITIAL_TOKEN_ENDPOINT", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
