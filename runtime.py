import ipaddress
import os
import re
import signal
import subprocess
import sys
import time


def configure() -> None:
    defaults = {
        "WEB_HTTP_PORT": os.getenv("WEB_PORT", "26665"),
        "WEB_HTTPS_PORT": "26666",
        "APP_PORT": "18080",
    }
    ports = []
    for name, default in defaults.items():
        value = os.getenv(name, default)
        if not value.isascii() or not value.isdigit() or not 1 <= int(value) <= 65535:
            raise ValueError(f"{name} must be a port between 1 and 65535")
        os.environ[name] = str(int(value))
        ports.append(int(value))
    if len(set(ports)) != len(ports):
        raise ValueError("HTTP, HTTPS and internal APP_PORT must be different")
    host = os.getenv("TLS_HOST", "localhost")
    try:
        address = ipaddress.ip_address(host)
        if address.version != 4:
            raise ValueError("TLS_HOST currently supports IPv4 or a hostname")
    except ValueError:
        if len(host) > 253 or not all(
            re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
            for label in host.split(".")
        ) or ":" in host:
            raise ValueError("TLS_HOST must be an IPv4 address or hostname, without a scheme or port")
    os.environ["TLS_HOST"] = host


def main() -> int:
    configure()
    children = []
    stopping = False

    def request_stop(signum, frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    try:
        children.append(subprocess.Popen([
            sys.executable, "-m", "uvicorn", "web.app.main:app",
            "--host", "127.0.0.1", "--port", os.environ["APP_PORT"],
        ]))
        children.append(subprocess.Popen([
            "caddy", "run", "--config", "/etc/netwake/Caddyfile", "--adapter", "caddyfile",
        ]))
        while not stopping:
            for child in children:
                if child.poll() is not None:
                    print(f"Service exited with code {child.returncode}; stopping container", flush=True)
                    return child.returncode or 1
            time.sleep(0.2)
        return 0
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
        deadline = time.monotonic() + 10
        for child in reversed(children):
            try:
                child.wait(timeout=max(0.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == "__main__":
    sys.exit(main())
