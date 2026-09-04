import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config import config
from app.models.schema import VideoAspect
from app.services import material


class TestTlsVerifyToggle(unittest.TestCase):
    """`tls_verify` decides whether material search/download validates
    certificates. It must default to ON and only turn off for values a user
    clearly meant as "false" — anything looser silently removes MITM
    protection from every stock-footage request."""

    def setUp(self):
        self.original_app = dict(config.app)

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app)

    def test_defaults_to_enabled_when_unset(self):
        config.app.pop("tls_verify", None)

        self.assertTrue(material._get_tls_verify())

    def test_boolean_true_enables_verification(self):
        config.app["tls_verify"] = True

        self.assertTrue(material._get_tls_verify())

    def test_boolean_false_disables_verification(self):
        config.app["tls_verify"] = False

        self.assertFalse(material._get_tls_verify())

    def test_falsey_strings_disable_verification(self):
        # TOML users may quote the value.
        for value in ("false", "False", "FALSE", "0", "no", "off", "  off  "):
            with self.subTest(value=value):
                config.app["tls_verify"] = value
                self.assertFalse(material._get_tls_verify())

    def test_other_strings_keep_verification_on(self):
        # Anything ambiguous must fail safe, not fail open.
        for value in ("true", "yes", "1", "on", "", "maybe"):
            with self.subTest(value=value):
                config.app["tls_verify"] = value
                self.assertTrue(material._get_tls_verify())

    def test_disabling_emits_a_warning(self):
        config.app["tls_verify"] = False
        messages = []
        handler_id = material.logger.add(lambda m: messages.append(m.record["message"]))
        try:
            material._get_tls_verify()
        finally:
            material.logger.remove(handler_id)

        self.assertTrue(
            any("TLS certificate verification is disabled" in m for m in messages)
        )

    def test_return_value_is_a_real_bool(self):
        # It is passed straight to requests' `verify=`.
        config.app["tls_verify"] = "off"

        self.assertIsInstance(material._get_tls_verify(), bool)


class TestSearchRequestsUseTlsVerify(unittest.TestCase):
    """Every outbound search must actually pass the resolved value through."""

    def setUp(self):
        self.original_app = dict(config.app)
        self.original_proxy = dict(config.proxy)
        config.proxy.clear()
        config.app["pexels_api_keys"] = ["k"]
        config.app["pixabay_api_keys"] = ["k"]
        config.app["coverr_api_keys"] = ["k"]

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app)
        config.proxy.clear()
        config.proxy.update(self.original_proxy)

    def _verify_kwarg(self, search_fn, payload):
        response = SimpleNamespace(json=lambda: payload)
        with patch.object(material.requests, "get", return_value=response) as get:
            search_fn(
                search_term="cat",
                minimum_duration=3,
                video_aspect=VideoAspect.portrait,
            )
        return get.call_args.kwargs["verify"]

    def test_all_providers_pass_verify_true_by_default(self):
        config.app.pop("tls_verify", None)
        cases = (
            (material.search_videos_pexels, {"videos": []}),
            (material.search_videos_pixabay, {"hits": []}),
            (material.search_videos_coverr, {"hits": []}),
        )
        for search_fn, payload in cases:
            with self.subTest(provider=search_fn.__name__):
                self.assertTrue(self._verify_kwarg(search_fn, payload))

    def test_all_providers_honour_an_explicit_opt_out(self):
        config.app["tls_verify"] = False
        cases = (
            (material.search_videos_pexels, {"videos": []}),
            (material.search_videos_pixabay, {"hits": []}),
            (material.search_videos_coverr, {"hits": []}),
        )
        for search_fn, payload in cases:
            with self.subTest(provider=search_fn.__name__):
                self.assertFalse(self._verify_kwarg(search_fn, payload))


if __name__ == "__main__":
    unittest.main()
