import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from web.app import auth, database
from web.app.api import system
from web.app import main


class LanWakeApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.db_patch = patch.object(database, "DB_PATH", str(self.db_path))
        self.token_patch = patch.object(auth, "APP_TOKEN", "test-admin-token-0123456789abcdef")
        self.public_token_patch = patch.object(
            system, "APP_TOKEN", "test-admin-token-0123456789abcdef"
        )
        self.initial_token_endpoint_patch = patch.object(
            system, "ALLOW_INITIAL_TOKEN_ENDPOINT", True
        )
        self.db_patch.start()
        self.token_patch.start()
        self.public_token_patch.start()
        self.initial_token_endpoint_patch.start()
        self.client_context = TestClient(main.app)
        self.client = self.client_context.__enter__()
        self.headers = {"X-Admin-Token": "test-admin-token-0123456789abcdef"}

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)
        self.public_token_patch.stop()
        self.initial_token_endpoint_patch.stop()
        self.token_patch.stop()
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def test_static_shell_and_public_config_load_without_token(self) -> None:
        page = self.client.get("/")
        config = self.client.get("/api/config")

        self.assertEqual(page.status_code, 200)
        self.assertIn("LanWake Hub", page.text)
        self.assertTrue(config.json()["auth_enabled"])

    def test_api_documentation_is_disabled(self) -> None:
        for path in ("/openapi.json", "/docs", "/docs/", "/redoc", "/redoc/"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_device_api_requires_token(self) -> None:
        response = self.client.get("/api/devices")
        self.assertEqual(response.status_code, 401)

    def test_initial_token_is_shown_once_and_requires_admin_confirmation(self) -> None:
        initial = self.client.get("/api/setup/initial-token")
        self.assertEqual(initial.status_code, 200)
        self.assertEqual(initial.json()["token"], "test-admin-token-0123456789abcdef")

        confirmed = self.client.post(
            "/api/setup/token-saved",
            headers=self.headers,
        )
        self.assertEqual(confirmed.status_code, 204)
        self.assertEqual(self.client.get("/api/setup/initial-token").status_code, 404)

    def test_create_device_and_reject_duplicate_mac(self) -> None:
        payload = {"name": "Office PC", "mac": "aa-bb-cc-dd-ee-02", "wol_status": "verified"}

        created = self.client.post("/api/devices", json=payload, headers=self.headers)
        duplicate = self.client.post("/api/devices", json=payload, headers=self.headers)

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["mac"], "AA:BB:CC:DD:EE:02")
        self.assertEqual(duplicate.status_code, 409)

    def test_scan_marks_missing_devices_offline_and_saves_broadcast(self) -> None:
        scan_result = {
            "cidr": "192.168.0.0/24",
            "interface": "eth0",
            "duration_ms": 12,
            "devices": [{
                "ip": "192.168.0.101",
                "mac": "AA:BB:CC:DD:EE:10",
                "hostname": "office-pc",
                "interface": "eth0",
                "source": "arp",
            }],
        }
        with patch("web.app.services.discovery.agent_request", return_value=scan_result):
            first = self.client.post(
                "/api/discovery/scan",
                json={"cidr": "192.168.0.0/24"},
                headers=self.headers,
            )
        self.assertEqual(first.status_code, 200)
        device = self.client.get("/api/devices", headers=self.headers).json()[0]
        self.assertTrue(device["is_online"])
        self.assertEqual(device["broadcast"], "192.168.0.255")
        self.assertEqual(device["name"], "office-pc")

        self.client.patch(
            f"/api/devices/{device['id']}",
            json={"name": "My desktop"},
            headers=self.headers,
        )
        scan_result["devices"][0]["hostname"] = "new-netbios-name"

        scan_result["devices"] = [{
            "ip": "192.168.0.101",
            "mac": "AA:BB:CC:DD:EE:10",
            "hostname": "new-netbios-name",
            "interface": "eth0",
            "source": "arp",
        }]
        with patch("web.app.services.discovery.agent_request", return_value=scan_result):
            second = self.client.post(
                "/api/discovery/scan",
                json={"cidr": "192.168.0.0/24"},
                headers=self.headers,
            )
        self.assertEqual(second.status_code, 200)
        device = self.client.get("/api/devices", headers=self.headers).json()[0]
        self.assertTrue(device["is_online"])
        self.assertEqual(device["name"], "My desktop")
        self.assertEqual(device["hostname"], "new-netbios-name")

        scan_result["devices"] = []
        with patch("web.app.services.discovery.agent_request", return_value=scan_result):
            third = self.client.post(
                "/api/discovery/scan",
                json={"cidr": "192.168.0.0/24"},
                headers=self.headers,
            )
        self.assertEqual(third.status_code, 200)
        device = self.client.get("/api/devices", headers=self.headers).json()[0]
        self.assertFalse(device["is_online"])

    def test_scan_interfaces_are_available_through_admin_api(self) -> None:
        interfaces = {"interfaces": [{"name": "eth0", "ipv4": "192.168.0.111", "cidr": "192.168.0.0/24"}]}
        with patch("web.app.api.discovery.agent_request", return_value=interfaces) as request:
            response = self.client.get("/api/discovery/interfaces", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), interfaces)
        request.assert_called_once_with("GET", "/v1/interfaces")

    def test_invalid_wol_status_is_rejected(self) -> None:
        response = self.client.post(
            "/api/devices",
            json={"mac": "AA:BB:CC:DD:EE:01", "wol_status": "maybe"},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 422)

    def test_mac_and_ip_are_strictly_validated(self) -> None:
        malformed_mac = self.client.post(
            "/api/devices",
            json={"mac": "GG:AA:BB:CC:DD:EE"},
            headers=self.headers,
        )
        public_ip = self.client.post(
            "/api/devices",
            json={"mac": "AA:BB:CC:DD:EE:03", "ip": "8.8.8.8"},
            headers=self.headers,
        )
        self.assertEqual(malformed_mac.status_code, 422)
        self.assertEqual(public_ip.status_code, 422)

    def test_required_device_fields_cannot_be_cleared_with_null(self) -> None:
        created = self.client.post(
            "/api/devices",
            json={"mac": "AA:BB:CC:DD:EE:04"},
            headers=self.headers,
        )
        response = self.client.patch(
            f"/api/devices/{created.json()['id']}",
            json={"notes": None},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 422)

    def test_wake_records_packet_sent_without_claiming_online(self) -> None:
        created = self.client.post(
            "/api/devices",
            json={
                "name": "Office PC",
                "mac": "AA:BB:CC:DD:EE:05",
                "ip": "192.168.0.101",
                "broadcast": "192.168.0.255",
            },
            headers=self.headers,
        )
        agent_result = {
            "packet_sent": True,
            "bytes_sent": 102,
            "mac": "AA:BB:CC:DD:EE:05",
            "broadcast": "192.168.0.255",
            "port": 9,
        }
        with patch("web.app.services.wol.agent_request", return_value=agent_result) as request:
            response = self.client.post(
                f"/api/devices/{created.json()['id']}/wake",
                headers=self.headers,
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["result"]["packet_sent"])
        self.assertEqual(request.call_args.args[2]["broadcast"], "192.168.0.255")
        device = self.client.get("/api/devices", headers=self.headers).json()[0]
        self.assertFalse(device["is_online"])

    def test_scan_rejects_untrusted_agent_range(self) -> None:
        from fastapi import HTTPException
        from web.app.services.discovery import merge_scan

        with self.assertRaises(HTTPException) as raised:
            merge_scan({"cidr": "8.8.8.0/24", "devices": []})
        self.assertEqual(raised.exception.status_code, 502)


if __name__ == "__main__":
    unittest.main()
