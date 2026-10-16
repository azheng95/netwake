import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from agent import agent as agent_app
from agent.schemas import ProbeRequest, WakeRequest
from agent.services.discovery import list_interfaces, scan_network
from agent.services.probe import probe_host
from agent.services.wol import send_magic_packet


class AgentTests(unittest.TestCase):
    def test_magic_packet_has_correct_payload_and_destination(self) -> None:
        fake_socket = MagicMock()
        fake_socket.__enter__.return_value = fake_socket
        fake_socket.sendto.side_effect = lambda packet, destination: len(packet)
        with patch("agent.services.wol.socket.socket", return_value=fake_socket) as socket_factory:
            result = send_magic_packet("aa:bb:cc:dd:ee:ff", "192.168.0.255", 9)

        packet = socket_factory.return_value.sendto.call_args.args[0]
        destination = socket_factory.return_value.sendto.call_args.args[1]
        self.assertEqual(len(packet), 102)
        self.assertEqual(packet[:6], b"\xff" * 6)
        self.assertEqual(packet[6:], bytes.fromhex("AABBCCDDEEFF") * 16)
        self.assertEqual(destination, ("192.168.0.255", 9))
        self.assertTrue(result["packet_sent"])

    def test_agent_schemas_reject_malformed_or_external_targets(self) -> None:
        with self.assertRaises(ValueError):
            WakeRequest(mac="not-a-mac")
        with self.assertRaises(ValueError):
            ProbeRequest(ip="8.8.8.8")
        with self.assertRaises(ValueError):
            WakeRequest(mac="AA:BB:CC:DD:EE:FF", broadcast="127.0.0.1")

    def test_scan_deduplicates_responses_and_requires_on_link_range(self) -> None:
        response = SimpleNamespace(psrc="192.168.0.20", hwsrc="aa:bb:cc:dd:ee:20")
        scapy = SimpleNamespace(
            conf=SimpleNamespace(iface="eth0"),
            get_if_list=lambda: ["eth0"],
            get_if_addr=lambda _: "192.168.0.111",
            Ether=MagicMock(),
            ARP=MagicMock(),
            srp=lambda *args, **kwargs: ([(None, response), (None, response)], []),
        )
        scapy.conf.route = SimpleNamespace(
            route=lambda _: ("eth0", "192.168.0.111", "0.0.0.0")
        )
        with (
            patch("agent.services.discovery._scapy", return_value=scapy),
            patch(
                "agent.services.discovery._resolve_netbios_hostnames",
                return_value={"192.168.0.20": "OFFICE-PC"},
            ),
        ):
            result = scan_network("192.168.0.0/24", None, "eth0", 0.2)
        self.assertEqual(len(result["devices"]), 1)
        self.assertEqual(result["devices"][0]["mac"], "AA:BB:CC:DD:EE:20")
        self.assertEqual(result["devices"][0]["hostname"], "OFFICE-PC")

        with patch("agent.services.discovery._scapy", return_value=scapy):
            with self.assertRaises(Exception):
                scan_network("192.168.1.0/24", None, "eth0", 0.2)

    def test_interface_list_includes_only_safe_private_scan_ranges(self) -> None:
        scapy = SimpleNamespace(
            get_if_list=lambda: ["eth0", "docker0", "lo"],
            get_if_addr=lambda name: {
                "eth0": "192.168.0.111",
                "docker0": "172.17.0.1",
                "lo": "127.0.0.1",
            }[name],
        )
        with (
            patch("agent.services.discovery._scapy", return_value=scapy),
            patch("agent.services.discovery._linux_interface_netmask", side_effect=lambda name: {
                "eth0": "255.255.255.0",
                "docker0": "255.255.0.0",
                "lo": "255.0.0.0",
            }[name]),
        ):
            interfaces = list_interfaces()

        self.assertEqual(interfaces[0]["cidr"], "192.168.0.0/24")
        self.assertIsNone(interfaces[1]["cidr"])
        self.assertIsNone(interfaces[2]["cidr"])

    def test_connection_refused_still_confirms_host_is_online(self) -> None:
        with patch(
            "agent.services.probe.socket.create_connection",
            side_effect=ConnectionRefusedError,
        ):
            result = probe_host("192.168.0.101", [22], 0.2)
        self.assertTrue(result["online"])
        self.assertEqual(result["method"], "tcp:22:refused")

    def test_agent_api_requires_shared_token(self) -> None:
        with patch.object(agent_app, "AGENT_TOKEN", "agent-test-token-0123456789abcdef"):
            with patch("agent.agent.list_interfaces", return_value=[]):
                with TestClient(agent_app.app) as client:
                    denied = client.get("/v1/interfaces")
                    allowed = client.get(
                        "/v1/interfaces",
                        headers={"X-Agent-Token": "agent-test-token-0123456789abcdef"},
                    )
        self.assertEqual(denied.status_code, 401)
        self.assertEqual(allowed.status_code, 200)

    def test_agent_api_documentation_is_disabled(self) -> None:
        with patch.object(agent_app, "AGENT_TOKEN", "agent-test-token-0123456789abcdef"):
            with TestClient(agent_app.app) as client:
                for path in ("/openapi.json", "/docs", "/docs/", "/redoc", "/redoc/"):
                    with self.subTest(path=path):
                        self.assertEqual(client.get(path).status_code, 404)


if __name__ == "__main__":
    unittest.main()
