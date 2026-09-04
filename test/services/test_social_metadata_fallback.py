import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services import llm


class TestSocialPlatformResolution(unittest.TestCase):
    def test_known_platforms_resolve_to_themselves(self):
        for platform in llm.SOCIAL_PLATFORMS:
            with self.subTest(platform=platform):
                self.assertEqual(llm._resolve_social_platform(platform), platform)

    def test_unknown_platform_falls_back_to_the_default(self):
        for value in ("nope", "", None, "YOUTUBE"):
            with self.subTest(value=value):
                self.assertIn(
                    llm._resolve_social_platform(value), llm.SOCIAL_PLATFORMS
                )


class TestClampAndHashtags(unittest.TestCase):
    """Platform limits are real API limits — YouTube rejects a title over 100
    characters, so an unclamped value fails the publish rather than the render."""

    def test_clamp_truncates_to_the_limit(self):
        self.assertEqual(len(llm._clamp_text("x" * 500, 100)), 100)

    def test_clamp_leaves_short_text_alone(self):
        self.assertEqual(llm._clamp_text("short", 100), "short")

    def test_hashtags_are_prefixed_deduplicated_and_capped(self):
        result = llm._normalize_hashtags(["a", "#b", "a", "c", "d", "e"], 3)

        self.assertEqual(len(result), 3)
        self.assertTrue(all(tag.startswith("#") for tag in result))
        self.assertEqual(len(set(result)), len(result))

    def test_hashtags_never_double_prefix(self):
        for tag in llm._normalize_hashtags(["#already", "plain"], 5):
            with self.subTest(tag=tag):
                self.assertFalse(tag.startswith("##"))


class TestFallbackSocialMetadata(unittest.TestCase):
    """Used whenever the LLM is unavailable or returns an unusable shape, so it
    must always produce a publishable structure — the result is POSTed straight
    to Upload-Post as the video's title/description/tags."""

    def _fallback(self, subject, script="", platform="youtube_shorts"):
        return llm._fallback_social_metadata(subject, script, platform)

    def test_shape_is_always_complete(self):
        result = self._fallback("coffee", "a script")

        self.assertEqual(set(result), {"title", "caption", "hashtags"})
        self.assertIsInstance(result["title"], str)
        self.assertIsInstance(result["caption"], str)
        self.assertIsInstance(result["hashtags"], list)

    def test_subject_becomes_the_title(self):
        self.assertEqual(self._fallback("coffee shops")["title"], "coffee shops")

    def test_missing_subject_falls_back_to_the_first_sentence(self):
        result = self._fallback("", "First sentence here. Second sentence.")

        self.assertEqual(result["title"], "First sentence here.")

    def test_title_respects_the_platform_limit(self):
        for platform, spec in llm.SOCIAL_PLATFORMS.items():
            with self.subTest(platform=platform):
                result = self._fallback("x" * 500, platform=platform)
                self.assertLessEqual(len(result["title"]), spec["title_max"])

    def test_caption_respects_the_platform_limit(self):
        for platform, spec in llm.SOCIAL_PLATFORMS.items():
            with self.subTest(platform=platform):
                result = self._fallback("subject", "y" * 20000, platform=platform)
                self.assertLessEqual(len(result["caption"]), spec["caption_max"])

    def test_hashtag_count_respects_the_platform_limit(self):
        for platform, spec in llm.SOCIAL_PLATFORMS.items():
            with self.subTest(platform=platform):
                result = self._fallback("subject", platform=platform)
                self.assertLessEqual(len(result["hashtags"]), spec["hashtag_count"])

    def test_all_hashtags_are_prefixed(self):
        for tag in self._fallback("subject")["hashtags"]:
            with self.subTest(tag=tag):
                self.assertTrue(tag.startswith("#"))

    def test_empty_input_still_produces_a_usable_structure(self):
        result = self._fallback("", "")

        self.assertEqual(set(result), {"title", "caption", "hashtags"})
        self.assertTrue(result["hashtags"])

    def test_unknown_platform_uses_the_default_limits(self):
        result = self._fallback("x" * 500, platform="myspace")
        default = llm.SOCIAL_PLATFORMS[llm._resolve_social_platform("myspace")]

        self.assertLessEqual(len(result["title"]), default["title_max"])


if __name__ == "__main__":
    unittest.main()
