import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.asgi import resolve_cors_settings


class TestResolveCorsSettings(unittest.TestCase):
    def test_credentials_are_disabled_when_origins_are_unrestricted(self):
        # The dangerous combination is wildcard + credentials: Starlette then
        # echoes the caller's Origin and marks the response as credentialed.
        origins, allow_credentials = resolve_cors_settings("")

        self.assertEqual(origins, ["*"])
        self.assertFalse(allow_credentials)

    def test_explicit_allowlist_enables_credentials(self):
        origins, allow_credentials = resolve_cors_settings("https://studio.example")

        self.assertEqual(origins, ["https://studio.example"])
        self.assertTrue(allow_credentials)

    def test_whitespace_around_entries_is_stripped(self):
        # "a, b".split(",") yields " b", which never matches an Origin header.
        origins, _ = resolve_cors_settings("https://a.example, https://b.example")

        self.assertEqual(origins, ["https://a.example", "https://b.example"])

    def test_blank_entries_are_dropped(self):
        origins, allow_credentials = resolve_cors_settings("  ,  ")

        self.assertEqual(origins, ["*"])
        self.assertFalse(allow_credentials)


class TestCorsResponseHeaders(unittest.TestCase):
    """End-to-end check through the real middleware."""

    def _headers_for(self, raw_origins, request_origin):
        from starlette.applications import Starlette
        from starlette.middleware.cors import CORSMiddleware
        from starlette.responses import PlainTextResponse
        from starlette.routing import Route
        from starlette.testclient import TestClient

        origins, allow_credentials = resolve_cors_settings(raw_origins)
        app = Starlette(routes=[Route("/x", lambda r: PlainTextResponse("ok"))])
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=allow_credentials,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        return TestClient(app).get("/x", headers={"Origin": request_origin}).headers

    def test_arbitrary_origin_is_not_granted_credentials_by_default(self):
        headers = self._headers_for("", "https://evil.example")

        self.assertNotEqual(
            headers.get("access-control-allow-origin"), "https://evil.example"
        )
        self.assertIsNone(headers.get("access-control-allow-credentials"))

    def test_allowlisted_origin_still_gets_credentials(self):
        headers = self._headers_for("https://studio.example", "https://studio.example")

        self.assertEqual(
            headers.get("access-control-allow-origin"), "https://studio.example"
        )
        self.assertEqual(headers.get("access-control-allow-credentials"), "true")

    def test_origin_outside_the_allowlist_is_refused(self):
        headers = self._headers_for("https://studio.example", "https://evil.example")

        self.assertIsNone(headers.get("access-control-allow-origin"))


if __name__ == "__main__":
    unittest.main()
