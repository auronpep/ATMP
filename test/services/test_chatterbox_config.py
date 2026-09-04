import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config import config


class TestParseChatterboxVoices(unittest.TestCase):
    """Chatterbox is self-hosted, so its voice list is typed by the operator.

    It arrives either as a TOML array (from config.toml) or as a
    comma-separated string (from the WebUI text box), and the dropdown, the
    preview button and the generate flow all have to see the same shape.
    """

    @classmethod
    def setUpClass(cls):
        import webui.Main as webui_main

        cls.parse = staticmethod(webui_main._parse_chatterbox_voices)

    def test_list_input_is_normalised(self):
        self.assertEqual(self.parse(["alpha", "beta"]), ["alpha", "beta"])

    def test_comma_separated_string_is_split(self):
        self.assertEqual(self.parse("alpha, beta"), ["alpha", "beta"])

    def test_whitespace_and_empty_segments_are_dropped(self):
        self.assertEqual(self.parse("  alpha , , beta  "), ["alpha", "beta"])
        self.assertEqual(self.parse(["  ", "beta"]), ["beta"])

    def test_empty_inputs_yield_an_empty_list(self):
        for value in ([], "", None):
            with self.subTest(value=value):
                self.assertEqual(self.parse(value), [])

    def test_non_string_entries_are_coerced(self):
        # TOML arrays are not type-checked; a bare number must not crash the UI.
        self.assertEqual(self.parse([1, 2]), ["1", "2"])

    def test_both_input_forms_agree(self):
        self.assertEqual(self.parse("alpha, beta"), self.parse(["alpha", "beta"]))

    def test_result_is_always_a_list_of_strings(self):
        for value in (["a"], "a,b", None, "", [1], ["  "]):
            with self.subTest(value=value):
                result = self.parse(value)
                self.assertIsInstance(result, list)
                self.assertTrue(all(isinstance(v, str) for v in result))


class TestSyncChatterboxConfigFromSessionState(unittest.TestCase):
    """The preview button sits *above* the Chatterbox inputs in the page, so on
    a rerun it would otherwise read stale config. This syncs session state into
    config first — the comment on the function says exactly that."""

    @classmethod
    def setUpClass(cls):
        import webui.Main as webui_main

        cls.main = webui_main

    def setUp(self):
        self.original = dict(config.chatterbox)

    def tearDown(self):
        config.chatterbox.clear()
        config.chatterbox.update(self.original)

    def _sync(self, session_state):
        with patch.object(self.main.st, "session_state", session_state):
            self.main._sync_chatterbox_config_from_session_state()

    def test_values_typed_in_the_form_win_over_saved_config(self):
        config.chatterbox.update(
            {"base_url": "http://old", "model_id": "old-model", "api_key": "old-key"}
        )

        self._sync(
            {
                "chatterbox_base_url_input": "http://new",
                "chatterbox_model_input": "new-model",
                "chatterbox_api_key_input": "new-key",
                "chatterbox_voices_input": "alpha, beta",
            }
        )

        self.assertEqual(config.chatterbox["base_url"], "http://new")
        self.assertEqual(config.chatterbox["model_id"], "new-model")
        self.assertEqual(config.chatterbox["api_key"], "new-key")
        self.assertEqual(config.chatterbox["voices"], ["alpha", "beta"])

    def test_saved_config_is_kept_when_the_form_has_no_entry(self):
        config.chatterbox.update({"base_url": "http://saved", "model_id": "saved-model"})

        self._sync({})

        self.assertEqual(config.chatterbox["base_url"], "http://saved")
        self.assertEqual(config.chatterbox["model_id"], "saved-model")

    def test_blank_values_fall_back_to_defaults(self):
        config.chatterbox.clear()

        self._sync(
            {
                "chatterbox_base_url_input": "",
                "chatterbox_model_input": "",
                "chatterbox_voices_input": "",
            }
        )

        self.assertEqual(config.chatterbox["model_id"], self.main.DEFAULT_CHATTERBOX_MODEL)
        self.assertEqual(config.chatterbox["voices"], [])

    def test_surrounding_whitespace_is_trimmed(self):
        self._sync(
            {
                "chatterbox_base_url_input": "  http://spaced  ",
                "chatterbox_model_input": "  spaced-model  ",
            }
        )

        self.assertEqual(config.chatterbox["base_url"], "http://spaced")
        self.assertEqual(config.chatterbox["model_id"], "spaced-model")

    def test_voices_are_normalised_to_a_list(self):
        self._sync({"chatterbox_voices_input": "alpha, beta, gamma"})

        self.assertEqual(config.chatterbox["voices"], ["alpha", "beta", "gamma"])


if __name__ == "__main__":
    unittest.main()
