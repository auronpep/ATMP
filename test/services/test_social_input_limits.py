import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services import llm


class TestLimitSocialText(unittest.TestCase):
    """Second line of defence on prompt inputs.

    The API schema already caps these fields, but this guard exists for
    internal and WebUI callers that bypass Pydantic — its comment says the
    point is to stop over-long content reaching the model and blowing up token
    cost. It truncates rather than raising, so a long script still produces
    metadata instead of failing the publish step.
    """

    def test_short_text_passes_through(self):
        self.assertEqual(llm._limit_social_text("coffee", 500, "video_subject"), "coffee")

    def test_text_is_trimmed(self):
        self.assertEqual(llm._limit_social_text("  coffee  ", 500, "f"), "coffee")

    def test_over_long_text_is_truncated_not_rejected(self):
        result = llm._limit_social_text("x" * 5000, 500, "video_subject")

        self.assertEqual(len(result), 500)

    def test_none_and_empty_become_empty_string(self):
        for value in (None, "", "   "):
            with self.subTest(value=value):
                self.assertEqual(llm._limit_social_text(value, 500, "f"), "")

    def test_exact_length_is_kept_whole(self):
        text = "y" * 500

        self.assertEqual(llm._limit_social_text(text, 500, "f"), text)

    def test_limits_match_the_module_constants(self):
        subject = llm._limit_social_text("s" * 10000, llm.MAX_SOCIAL_SUBJECT_LENGTH, "s")
        script = llm._limit_social_text("t" * 20000, llm.MAX_SOCIAL_SCRIPT_LENGTH, "t")

        self.assertEqual(len(subject), llm.MAX_SOCIAL_SUBJECT_LENGTH)
        self.assertEqual(len(script), llm.MAX_SOCIAL_SCRIPT_LENGTH)


class TestNormalizeSocialLanguage(unittest.TestCase):
    """The language string is interpolated into the prompt, so an unbounded
    value is a prompt-injection surface as well as a token-cost one."""

    def test_known_codes_pass_through(self):
        for code in ("zh-CN", "en", "pt-BR"):
            with self.subTest(code=code):
                self.assertEqual(llm._normalize_social_language(code), code)

    def test_blank_and_none_fall_back_to_the_default(self):
        for value in ("", "   ", None):
            with self.subTest(value=value):
                self.assertEqual(
                    llm._normalize_social_language(value), llm.DEFAULT_SOCIAL_LANGUAGE
                )

    def test_whitespace_is_trimmed(self):
        self.assertEqual(llm._normalize_social_language("  fr  "), "fr")

    def test_over_long_values_are_truncated(self):
        result = llm._normalize_social_language("x" * 500)

        self.assertEqual(len(result), llm.MAX_SOCIAL_LANGUAGE_LENGTH)

    def test_result_is_never_empty(self):
        # It is interpolated into the prompt; an empty value would produce a
        # malformed instruction line.
        for value in (None, "", "   ", "en", "x" * 500):
            with self.subTest(value=value):
                self.assertTrue(llm._normalize_social_language(value))


class TestSocialMetadataRespectsLimits(unittest.TestCase):
    """End-to-end: over-long input still yields publishable metadata."""

    def setUp(self):
        from app.config import config

        self.config = config
        self.original_app = dict(config.app)

    def tearDown(self):
        self.config.app.clear()
        self.config.app.update(self.original_app)

    def test_huge_input_still_produces_a_complete_structure(self):
        # No LLM configured -> falls back to the heuristic path.
        self.config.app["llm_provider"] = "openai"
        self.config.app["openai_api_key"] = ""

        result = llm.generate_social_metadata(
            video_subject="s" * 10000,
            video_script="t" * 50000,
            platform="youtube_shorts",
        )

        self.assertEqual(set(result), {"title", "caption", "hashtags"})
        spec = llm.SOCIAL_PLATFORMS["youtube_shorts"]
        self.assertLessEqual(len(result["title"]), spec["title_max"])
        self.assertLessEqual(len(result["caption"]), spec["caption_max"])


if __name__ == "__main__":
    unittest.main()
