import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config import config
from app.services import twelvelabs


class TestDisabledIsACompleteNoOp(unittest.TestCase):
    """The module's headline promise:

        If `twelvelabs_api_keys` is not configured, every public function here
        is a no-op that returns its input unchanged (or None), so default
        behavior is identical to a build without TwelveLabs.

    TwelveLabs is an optional extra (`uv sync --extra twelvelabs`), so on a
    default install the SDK is not even importable. Any public function that
    reaches the client before checking `is_enabled()` would turn an opt-in
    feature into an ImportError on the main render path.
    """

    def setUp(self):
        self.original_app = dict(config.app)
        config.app.pop("twelvelabs_api_keys", None)
        config.app.pop("twelvelabs_rerank_terms", None)

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app)

    def test_is_enabled_is_false_without_keys(self):
        self.assertFalse(twelvelabs.is_enabled())

    def test_is_enabled_is_false_for_an_empty_key_list(self):
        config.app["twelvelabs_api_keys"] = []

        self.assertFalse(twelvelabs.is_enabled())

    def test_is_enabled_is_true_with_a_key(self):
        config.app["twelvelabs_api_keys"] = ["tlk_x"]

        self.assertTrue(twelvelabs.is_enabled())

    def test_rerank_returns_the_input_unchanged(self):
        terms = ["coffee shop", "latte art"]

        with patch.object(twelvelabs, "_client") as client:
            result = twelvelabs.rerank_terms_by_subject("coffee", terms)

        self.assertEqual(result, terms)
        client.assert_not_called()

    def test_embed_text_returns_none_without_touching_the_client(self):
        with patch.object(twelvelabs, "_client") as client:
            self.assertIsNone(twelvelabs.embed_text("coffee"))
        client.assert_not_called()

    def test_analyze_clip_returns_none_without_touching_the_client(self):
        with patch.object(twelvelabs, "_client") as client:
            self.assertIsNone(twelvelabs.analyze_clip("https://x/y.mp4"))
        client.assert_not_called()

    def test_no_public_function_imports_the_optional_sdk_when_disabled(self):
        # The SDK is an optional extra; importing it on the default path would
        # break installs that never opted in.
        with patch.dict(sys.modules, {"twelvelabs": None, "twelvelabs.types": None}):
            self.assertEqual(twelvelabs.rerank_terms_by_subject("s", ["a", "b"]), ["a", "b"])
            self.assertIsNone(twelvelabs.embed_text("a"))
            self.assertIsNone(twelvelabs.analyze_clip("https://x/y.mp4"))


class TestEnabledButFeatureFlagOff(unittest.TestCase):
    """A configured key alone must not turn on reranking — that has its own
    opt-in flag, because it costs an API call per search term."""

    def setUp(self):
        self.original_app = dict(config.app)
        config.app["twelvelabs_api_keys"] = ["tlk_x"]
        config.app.pop("twelvelabs_rerank_terms", None)

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app)

    def test_rerank_is_skipped_without_its_flag(self):
        terms = ["a", "b"]

        with patch.object(twelvelabs, "_client") as client:
            self.assertEqual(twelvelabs.rerank_terms_by_subject("s", terms), terms)
        client.assert_not_called()

    def test_rerank_needs_at_least_two_terms(self):
        config.app["twelvelabs_rerank_terms"] = True

        with patch.object(twelvelabs, "_client") as client:
            self.assertEqual(twelvelabs.rerank_terms_by_subject("s", ["only"]), ["only"])
        client.assert_not_called()

    def test_rerank_needs_a_subject(self):
        config.app["twelvelabs_rerank_terms"] = True

        with patch.object(twelvelabs, "_client") as client:
            self.assertEqual(twelvelabs.rerank_terms_by_subject("", ["a", "b"]), ["a", "b"])
        client.assert_not_called()

    def test_embed_text_ignores_blank_input(self):
        with patch.object(twelvelabs, "_client") as client:
            self.assertIsNone(twelvelabs.embed_text(""))
            self.assertIsNone(twelvelabs.embed_text("   "))
        client.assert_not_called()

    def test_analyze_clip_ignores_a_blank_url(self):
        with patch.object(twelvelabs, "_client") as client:
            self.assertIsNone(twelvelabs.analyze_clip(""))
        client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
