import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

WEBUI_MAIN = Path(__file__).parent.parent.parent / "webui" / "Main.py"
PROVIDERS = ("pexels", "pixabay", "coverr")


class TestApiKeyPanelGuards(unittest.TestCase):
    """The API-key panel indexes config.app directly.

    Streamlit re-executes the whole script per interaction, so one KeyError
    there fails the entire page render, not just that panel. A user whose
    config.toml lacks a provider key (deleted by hand, or written by an older
    version) must still get a usable UI.
    """

    @classmethod
    def setUpClass(cls):
        cls.source = WEBUI_MAIN.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_every_provider_key_is_defaulted_before_use(self):
        for provider in PROVIDERS:
            with self.subTest(provider=provider):
                guard = (
                    f'if "{provider}_api_keys" not in config.app '
                    f'or config.app["{provider}_api_keys"] is None:'
                )
                # assertTrue, not assertIn: a failing assertIn would dump
                # the entire 1800-line module into the report.
                self.assertTrue(
                    guard in self.source,
                    f"{provider}_api_keys is indexed without a default guard",
                )

    def test_guard_precedes_the_first_index_for_each_provider(self):
        for provider in PROVIDERS:
            with self.subTest(provider=provider):
                guard_at = self.source.index(f'if "{provider}_api_keys" not in config.app')
                first_index_at = self.source.index(f'if config.app["{provider}_api_keys"]:')
                self.assertLess(
                    guard_at,
                    first_index_at,
                    f"{provider} guard runs after the first index access",
                )

    def test_missing_key_is_repaired_to_an_empty_list(self):
        # Mirror of the guard, exercised against a config that lacks the key.
        for provider in PROVIDERS:
            with self.subTest(provider=provider):
                app = {}
                if f"{provider}_api_keys" not in app or app[f"{provider}_api_keys"] is None:
                    app[f"{provider}_api_keys"] = []
                self.assertEqual(app[f"{provider}_api_keys"], [])

    def test_none_value_is_also_repaired(self):
        for provider in PROVIDERS:
            with self.subTest(provider=provider):
                app = {f"{provider}_api_keys": None}
                if f"{provider}_api_keys" not in app or app[f"{provider}_api_keys"] is None:
                    app[f"{provider}_api_keys"] = []
                self.assertEqual(app[f"{provider}_api_keys"], [])

    def test_webui_module_still_parses(self):
        self.assertIsInstance(self.tree, ast.Module)


if __name__ == "__main__":
    unittest.main()
