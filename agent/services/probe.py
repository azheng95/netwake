import subprocess
import socket


def probe_host(ip: str, ports: list[int], timeout: float) -> dict:
    for port in ports:
        try:
            with socket.create_connection((ip, port), timeout=timeout):
                return {"ip": ip, "online": True, "method": f"tcp:{port}"}
        except ConnectionRefusedError:
            return {"ip": ip, "online": True, "method": f"tcp:{port}:refused"}
        except OSError:
            continue

    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(max(1, int(timeout))), ip],
            capture_output=True,
            timeout=max(2, int(timeout) + 1),
            check=False,
        )
        if result.returncode == 0:
            return {"ip": ip, "online": True, "method": "icmp"}
    except (FileNotFoundError, subprocess.SubprocessError):
        pass
    return {"ip": ip, "online": False, "method": None}
