import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

REPO_ROOT = Path(__file__).parent.parent.parent


class TestPingEndpoint(unittest.TestCase):
    """`app/controllers/ping.py` defined /ping but its router was never
    included, so the service had no health endpoint for an orchestrator to
    probe."""

    @classmethod
    def setUpClass(cls):
        from starlette.testclient import TestClient

        from app.asgi import app

        cls.client = TestClient(app, raise_server_exceptions=False)

    def test_ping_is_reachable(self):
        response = self.client.get("/ping")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), "pong")

    def test_ping_needs_no_version_prefix(self):
        # Health probes are configured by hand in compose/k8s; keeping it off
        # the /api/v1 prefix means it survives an API version bump.
        self.assertEqual(self.client.get("/api/v1/ping").status_code, 404)

    def test_ping_is_listed_in_the_openapi_schema(self):
        paths = self.client.get("/openapi.json").json()["paths"]

        self.assertIn("/ping", paths)

    def test_existing_v1_routes_still_resolve(self):
        # Registering a second router must not shadow the versioned ones.
        paths = self.client.get("/openapi.json").json()["paths"]

        for path in ("/api/v1/videos", "/api/v1/tasks", "/api/v1/musics"):
            with self.subTest(path=path):
                self.assertIn(path, paths)


class TestComposeHealthchecks(unittest.TestCase):
    def _services(self, filename):
        import yaml

        data = yaml.safe_load((REPO_ROOT / filename).read_text(encoding="utf-8"))
        return data["services"]

    def test_both_compose_files_probe_both_services(self):
        for filename in ("docker-compose.yml", "docker-compose.release.yml"):
            for name in ("webui", "api"):
                with self.subTest(filename=filename, service=name):
                    healthcheck = self._services(filename)[name].get("healthcheck")
                    self.assertIsNotNone(healthcheck)
                    self.assertIn("test", healthcheck)

    def test_api_probe_targets_the_ping_route(self):
        for filename in ("docker-compose.yml", "docker-compose.release.yml"):
            with self.subTest(filename=filename):
                probe = " ".join(self._services(filename)["api"]["healthcheck"]["test"])
                self.assertIn("8080/ping", probe)

    def test_webui_probe_targets_the_streamlit_health_route(self):
        for filename in ("docker-compose.yml", "docker-compose.release.yml"):
            with self.subTest(filename=filename):
                probe = " ".join(self._services(filename)["webui"]["healthcheck"]["test"])
                self.assertIn("8501/_stcore/health", probe)

    def test_probe_uses_python_which_the_image_is_guaranteed_to_have(self):
        # The image installs git/imagemagick/ffmpeg but not curl or wget.
        probe = self._services("docker-compose.yml")["api"]["healthcheck"]["test"]

        self.assertEqual(probe[0], "CMD")
        self.assertEqual(probe[1], "python3")


if __name__ == "__main__":
    unittest.main()
