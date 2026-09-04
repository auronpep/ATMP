import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config import config


class TestIsRunningInContainer(unittest.TestCase):
    """Decides the default Ollama base_url, so a false positive on a plain
    Linux host silently points the app at host.docker.internal."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.missing = os.path.join(self._tmp.name, "nope")

    def _cgroup(self, content):
        path = os.path.join(self._tmp.name, "cgroup")
        Path(path).write_text(content, encoding="utf-8")
        return path

    def _detect(self, *, dockerenv=None, containerenv=None, cgroup=None):
        return config.is_running_in_container(
            dockerenv_path=dockerenv or self.missing,
            containerenv_path=containerenv or self.missing,
            cgroup_path=cgroup or self.missing,
        )

    def test_dockerenv_marker_file_is_enough(self):
        marker = os.path.join(self._tmp.name, ".dockerenv")
        Path(marker).write_text("", encoding="utf-8")

        self.assertTrue(self._detect(dockerenv=marker))

    def test_podman_containerenv_marker_file_is_enough(self):
        marker = os.path.join(self._tmp.name, ".containerenv")
        Path(marker).write_text("", encoding="utf-8")

        self.assertTrue(self._detect(containerenv=marker))

    def test_known_container_runtimes_are_detected_from_cgroup(self):
        for marker in ("docker", "containerd", "kubepods", "libpod", "podman"):
            with self.subTest(marker=marker):
                cgroup = self._cgroup(f"12:memory:/{marker}/abc123\n")
                self.assertTrue(self._detect(cgroup=cgroup))

    def test_cgroup_matching_is_case_insensitive(self):
        cgroup = self._cgroup("12:memory:/KUBEPODS/pod-1\n")

        self.assertTrue(self._detect(cgroup=cgroup))

    def test_plain_linux_host_is_not_a_container(self):
        # A normal Linux box has /proc/1/cgroup too; only explicit runtime
        # markers may count, otherwise every Linux user gets the Docker default.
        cgroup = self._cgroup("12:memory:/init.scope\n11:cpu:/user.slice\n")

        self.assertFalse(self._detect(cgroup=cgroup))

    def test_missing_cgroup_file_is_not_a_container(self):
        self.assertFalse(self._detect())

    def test_unreadable_cgroup_file_is_not_a_container(self):
        cgroup = self._cgroup("docker\n")
        with patch("builtins.open", side_effect=PermissionError("denied")):
            self.assertFalse(self._detect(cgroup=cgroup))


class TestContainerDefaultGatewayIp(unittest.TestCase):
    """/proc/net/route stores the gateway as little-endian hex."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _route(self, body):
        path = os.path.join(self._tmp.name, "route")
        header = "Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask\n"
        Path(path).write_text(header + body, encoding="utf-8")
        return path

    def test_decodes_the_default_route_gateway(self):
        # 010011AC -> 172.17.0.1, the usual docker0 bridge gateway
        route = self._route("eth0\t00000000\t010011AC\t0003\t0\t0\t0\t00000000\n")

        self.assertEqual(config.get_container_default_gateway_ip(route), "172.17.0.1")

    def test_skips_non_default_routes(self):
        route = self._route(
            "eth0\t000011AC\t00000000\t0001\t0\t0\t0\t0000FFFF\n"
            "eth0\t00000000\t0101A8C0\t0003\t0\t0\t0\t00000000\n"
        )

        self.assertEqual(config.get_container_default_gateway_ip(route), "192.168.1.1")

    def test_default_route_without_a_gateway_is_ignored(self):
        route = self._route("eth0\t00000000\t00000000\t0001\t0\t0\t0\t00000000\n")

        self.assertEqual(config.get_container_default_gateway_ip(route), "")

    def test_malformed_gateway_field_returns_empty(self):
        route = self._route("eth0\t00000000\tZZZ\t0003\t0\t0\t0\t00000000\n")

        self.assertEqual(config.get_container_default_gateway_ip(route), "")

    def test_short_lines_are_skipped(self):
        route = self._route("eth0\t00000000\n")

        self.assertEqual(config.get_container_default_gateway_ip(route), "")

    def test_missing_route_file_returns_empty(self):
        self.assertEqual(
            config.get_container_default_gateway_ip(
                os.path.join(self._tmp.name, "absent")
            ),
            "",
        )


class TestDefaultOllamaBaseUrl(unittest.TestCase):
    def test_host_run_uses_localhost(self):
        with patch.object(config, "is_running_in_container", return_value=False):
            self.assertEqual(
                config.get_default_ollama_base_url(), "http://localhost:11434/v1"
            )

    def test_container_prefers_host_docker_internal_when_resolvable(self):
        with patch.object(config, "is_running_in_container", return_value=True), patch.object(
            config, "_can_resolve_hostname", return_value=True
        ):
            self.assertEqual(
                config.get_default_ollama_base_url(),
                "http://host.docker.internal:11434/v1",
            )

    def test_container_falls_back_to_the_default_gateway(self):
        with patch.object(config, "is_running_in_container", return_value=True), patch.object(
            config, "_can_resolve_hostname", return_value=False
        ), patch.object(
            config, "get_container_default_gateway_ip", return_value="172.17.0.1"
        ):
            self.assertEqual(
                config.get_default_ollama_base_url(), "http://172.17.0.1:11434/v1"
            )

    def test_container_without_a_gateway_still_returns_a_usable_url(self):
        with patch.object(config, "is_running_in_container", return_value=True), patch.object(
            config, "_can_resolve_hostname", return_value=False
        ), patch.object(config, "get_container_default_gateway_ip", return_value=""):
            self.assertEqual(
                config.get_default_ollama_base_url(),
                "http://host.docker.internal:11434/v1",
            )


if __name__ == "__main__":
    unittest.main()
