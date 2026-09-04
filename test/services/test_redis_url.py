import sys
import unittest
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestBuildRedisUrl(unittest.TestCase):
    """The Redis URL is assembled by hand, so the credential section has to be
    built defensively: an unset password must vanish and a set one must be
    percent-encoded before it reaches the authority section."""

    def setUp(self):
        from app.controllers.v1.video import _build_redis_url

        self.build = _build_redis_url

    def test_unset_password_is_omitted_not_stringified(self):
        # An f-string turns None into the literal password "None", which makes
        # AUTH fail against a password-less server.
        for empty in (None, ""):
            url = self.build("localhost", 6379, 0, empty)
            self.assertEqual(url, "redis://localhost:6379/0")
            self.assertIsNone(urlparse(url).password)
            self.assertNotIn("None", url)

    def test_password_with_url_delimiters_keeps_host_and_port_intact(self):
        # "@", ":" and "/" split the authority section when interpolated raw:
        # the parsed host/port silently becomes something else entirely.
        url = self.build("localhost", 6379, 0, "p@ss:w/rd")
        parsed = urlparse(url)
        self.assertEqual(parsed.hostname, "localhost")
        self.assertEqual(parsed.port, 6379)
        self.assertEqual(parsed.path, "/0")

    def test_encoded_password_round_trips_through_redis_parser(self):
        from redis.connection import parse_url

        password = "p@ss:w/rd"
        parsed = parse_url(self.build("localhost", 6379, 0, password))
        self.assertEqual(parsed["password"], password)
        self.assertEqual(parsed["host"], "localhost")
        self.assertEqual(parsed["port"], 6379)
        self.assertEqual(parsed["db"], 0)

    def test_simple_password_still_supported(self):
        url = self.build("redis.internal", 6380, 3, "simple")
        self.assertEqual(url, "redis://:simple@redis.internal:6380/3")


class TestModuleLevelRedisUrl(unittest.TestCase):
    """`redis_url` is assembled once at import time from config, so the
    regression has to be reproduced by reloading the module under a config
    that carries a password."""

    def setUp(self):
        from app.config import config

        self.config = config
        self.original_app_config = dict(config.app)

    def tearDown(self):
        self.config.app.clear()
        self.config.app.update(self.original_app_config)
        self._reload()

    def _reload(self):
        import importlib

        import app.controllers.v1.video as video_controller

        return importlib.reload(video_controller)

    def test_password_with_delimiters_does_not_corrupt_host_and_port(self):
        from redis.connection import parse_url

        self.config.app["enable_redis"] = False
        self.config.app["redis_host"] = "redis.internal"
        self.config.app["redis_port"] = 6379
        self.config.app["redis_db"] = 0
        self.config.app["redis_password"] = "p@ss:w/rd"

        parsed = parse_url(self._reload().redis_url)
        self.assertEqual(parsed["host"], "redis.internal")
        self.assertEqual(parsed["port"], 6379)
        self.assertEqual(parsed["password"], "p@ss:w/rd")

    def test_missing_password_does_not_send_the_string_none(self):
        from redis.connection import parse_url

        self.config.app["enable_redis"] = False
        self.config.app["redis_host"] = "redis.internal"
        self.config.app["redis_port"] = 6379
        self.config.app["redis_db"] = 0
        self.config.app.pop("redis_password", None)

        parsed = parse_url(self._reload().redis_url)
        self.assertIsNone(parsed.get("password"))


if __name__ == "__main__":
    unittest.main()
