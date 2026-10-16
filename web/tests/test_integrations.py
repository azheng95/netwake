import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException

import runtime
from web.app.integrations import agent_request


class IntegratedLanTests(unittest.TestCase):
    def test_status_works_without_agent_token_or_network_call(self):
        with patch.dict(os.environ, {}, clear=True):
            status = agent_request("GET", "/healthz")
        self.assertTrue(status["ok"])
        self.assertEqual(status["version"], "1.0.0")

    def test_interfaces_call_local_backend(self):
        with patch("web.app.integrations.list_interfaces", return_value=[]) as backend:
            self.assertEqual(agent_request("GET", "/v1/interfaces"), {"interfaces": []})
        backend.assert_called_once_with()

    def test_scan_calls_local_backend(self):
        with (
            patch("web.app.integrations.SCAN_INTERFACE", "eth0"),
            patch("web.app.integrations.scan_network", return_value={}) as backend,
        ):
            agent_request("POST", "/v1/discovery/scan", {"cidr": "192.168.0.0/24"})
        backend.assert_called_once_with("192.168.0.0/24", None, "eth0", 2.0)

    def test_wake_and_probe_keep_input_validation(self):
        with patch("web.app.integrations.send_magic_packet", return_value={}) as backend:
            agent_request("POST", "/v1/wol", {"mac": "aa-bb-cc-dd-ee-02"})
        backend.assert_called_once_with("AA:BB:CC:DD:EE:02", None, 9)
        with patch("web.app.integrations.probe_host") as backend:
            with self.assertRaises(ValueError):
                agent_request("POST", "/v1/probe", {"ip": "8.8.8.8"})
        backend.assert_not_called()

    def test_unknown_operation_is_rejected(self):
        with self.assertRaises(HTTPException):
            agent_request("GET", "/v1/not-real")

    def test_runtime_rejects_invalid_ports_and_host(self):
        for settings in (
            {"WEB_HTTP_PORT": "0"},
            {"WEB_HTTPS_PORT": "not-a-port"},
            {"WEB_HTTP_PORT": "26666"},
            {"TLS_HOST": "https://192.168.0.111"},
            {"TLS_HOST": "localhost\nadmin off"},
        ):
            with self.subTest(settings=settings), patch.dict(os.environ, settings, clear=True):
                with self.assertRaises(ValueError):
                    runtime.configure()

    def test_runtime_defaults_and_custom_ports(self):
        with patch.dict(os.environ, {}, clear=True):
            runtime.configure()
            self.assertEqual(os.environ["WEB_HTTP_PORT"], "26665")
            self.assertEqual(os.environ["APP_PORT"], "18080")
        with patch.dict(os.environ, {
            "WEB_HTTP_PORT": "27665", "WEB_HTTPS_PORT": "27666",
            "TLS_HOST": "192.168.0.111",
        }, clear=True):
            runtime.configure()
            self.assertEqual(os.environ["WEB_HTTPS_PORT"], "27666")
