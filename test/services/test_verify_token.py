import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config import config
from app.controllers import base
from app.models.exception import HttpException


def _request(header_value=None, user_agent="pytest"):
    request = MagicMock()
    headers = {"user-agent": user_agent}
    if header_value is not None:
        headers["x-api-key"] = header_value
    request.headers = headers
    request.url = "http://localhost:8080/api/v1/videos"
    return request


class TestVerifyToken(unittest.TestCase):
    """`verify_token` is the opt-in auth dependency for the whole v1 router
    (`app/controllers/v1/video.py:37`). It must fail closed."""

    def setUp(self):
        self.original_app = dict(config.app)

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app)

    def _allowed(self, request):
        try:
            base.verify_token(request)
            return True
        except HttpException:
            return False

    def test_unconfigured_api_key_rejects_an_empty_header(self):
        # The bypass: "" == config.app.get("api_key", "") authenticated anyone
        # who sent an empty x-api-key, while a request with no header at all was
        # denied - so the endpoint looked protected.
        config.app.pop("api_key", None)

        self.assertFalse(self._allowed(_request("")))

    def test_explicitly_empty_api_key_rejects_an_empty_header(self):
        config.app["api_key"] = ""

        self.assertFalse(self._allowed(_request("")))

    def test_unconfigured_api_key_rejects_a_missing_header(self):
        config.app.pop("api_key", None)

        self.assertFalse(self._allowed(_request()))

    def test_unconfigured_api_key_rejects_any_token(self):
        config.app.pop("api_key", None)

        for token in ("", "guess", "None"):
            with self.subTest(token=token):
                self.assertFalse(self._allowed(_request(token)))

    def test_correct_token_is_accepted(self):
        config.app["api_key"] = "s3cret-token"

        self.assertTrue(self._allowed(_request("s3cret-token")))

    def test_wrong_token_is_rejected(self):
        config.app["api_key"] = "s3cret-token"

        for token in ("nope", "s3cret", "s3cret-token-extra", ""):
            with self.subTest(token=token):
                self.assertFalse(self._allowed(_request(token)))

    def test_missing_header_is_rejected_when_configured(self):
        config.app["api_key"] = "s3cret-token"

        self.assertFalse(self._allowed(_request()))

    def test_rejection_uses_a_401(self):
        config.app["api_key"] = "s3cret-token"

        with self.assertRaises(HttpException) as ctx:
            base.verify_token(_request("nope"))

        self.assertEqual(ctx.exception.status_code, 401)

    def test_comparison_is_constant_time(self):
        # secrets.compare_digest, not ==, so response timing can't be used to
        # recover the key one byte at a time.
        import inspect

        source = inspect.getsource(base.verify_token)
        self.assertIn("compare_digest", source)


if __name__ == "__main__":
    unittest.main()
