import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config import config
from app.services import material

SECRETS = {
    "openai_api_key": "sk-SECRET-openai-123",
    "elevenlabs_api_key": "el-SECRET-elevenlabs-456",
    "azure_speech_key": "az-SECRET-speech-789",
    "siliconflow_api_key": "sf-SECRET-flow-abc",
    "pixabay_api_keys": ["pb-SECRET-pixabay-def"],
}


class TestApiKeyErrorDoesNotLeakConfig(unittest.TestCase):
    """The "key is not set" error is logged by every caller, and the WebUI
    renders log records into the page with st.code(). It must not carry the
    rest of the configuration with it."""

    def setUp(self):
        self.original_app = dict(config.app)
        config.app.update(SECRETS)
        config.app["pexels_api_keys"] = []

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app)

    def _message(self):
        with self.assertRaises(ValueError) as ctx:
            material.get_api_key("pexels_api_keys")
        return str(ctx.exception)

    def test_no_configured_secret_appears_in_the_message(self):
        message = self._message()

        for name, value in SECRETS.items():
            expected = value[0] if isinstance(value, list) else value
            with self.subTest(setting=name):
                self.assertNotIn(expected, message)

    def test_message_still_names_the_missing_setting_and_config_file(self):
        message = self._message()

        self.assertIn("pexels_api_keys is not set", message)
        self.assertIn(config.config_file, message)

    def test_message_stays_short_enough_to_be_readable(self):
        # The old message embedded the whole config as JSON (~3 KB).
        self.assertLess(len(self._message()), 300)

    def test_a_configured_key_is_still_returned(self):
        config.app["pexels_api_keys"] = ["pexels-key-1"]

        self.assertEqual(material.get_api_key("pexels_api_keys"), "pexels-key-1")

    def test_string_form_is_still_supported(self):
        config.app["pexels_api_keys"] = "single-string-key"

        self.assertEqual(material.get_api_key("pexels_api_keys"), "single-string-key")

    def test_multiple_keys_rotate(self):
        config.app["pexels_api_keys"] = ["k0", "k1", "k2"]

        seen = {material.get_api_key("pexels_api_keys") for _ in range(9)}

        self.assertEqual(seen, {"k0", "k1", "k2"})


if __name__ == "__main__":
    unittest.main()
