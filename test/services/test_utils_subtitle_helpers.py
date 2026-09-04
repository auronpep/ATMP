import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.utils import utils

SRT_TIMESTAMP = re.compile(r"^\d{2}:\d{2}:\d{2},\d{3}$")


class TestSrtTimestampFormatting(unittest.TestCase):
    """Every SRT timestamp the project emits goes through this function.

    A malformed stamp makes the whole file unimportable in editing software,
    so the zero-padded HH:MM:SS,mmm shape is the contract.
    """

    def test_known_values(self):
        cases = {
            0: "00:00:00,000",
            1: "00:00:01,000",
            61.5: "00:01:01,500",
            3600: "01:00:00,000",
            3661.25: "01:01:01,250",
        }
        for seconds, expected in cases.items():
            with self.subTest(seconds=seconds):
                self.assertEqual(utils.time_convert_seconds_to_hmsm(seconds), expected)

    def test_rolls_over_at_minute_and_hour_boundaries(self):
        self.assertEqual(utils.time_convert_seconds_to_hmsm(59.999), "00:00:59,999")
        self.assertEqual(utils.time_convert_seconds_to_hmsm(60), "00:01:00,000")
        self.assertEqual(utils.time_convert_seconds_to_hmsm(3599.999), "00:59:59,999")
        self.assertEqual(utils.time_convert_seconds_to_hmsm(3600), "01:00:00,000")

    def test_output_is_always_zero_padded(self):
        for seconds in (0, 5, 65, 605, 3605, 7325.5):
            with self.subTest(seconds=seconds):
                self.assertRegex(
                    utils.time_convert_seconds_to_hmsm(seconds), SRT_TIMESTAMP
                )

    def test_milliseconds_never_reach_1000(self):
        for seconds in (0.9999, 1.9999, 59.9999):
            with self.subTest(seconds=seconds):
                stamp = utils.time_convert_seconds_to_hmsm(seconds)
                self.assertRegex(stamp, SRT_TIMESTAMP)
                self.assertLess(int(stamp.split(",")[1]), 1000)


class TestTextToSrt(unittest.TestCase):
    def test_emits_index_timespan_and_text(self):
        block = utils.text_to_srt(3, "Hello world", 1.0, 2.5)
        lines = block.splitlines()

        self.assertEqual(lines[0], "3")
        self.assertEqual(lines[1], "00:00:01,000 --> 00:00:02,500")
        self.assertEqual(lines[2], "Hello world")

    def test_timespan_uses_the_srt_arrow_separator(self):
        block = utils.text_to_srt(1, "x", 0.0, 1.0)

        self.assertIn(" --> ", block)
        start, end = block.splitlines()[1].split(" --> ")
        self.assertRegex(start, SRT_TIMESTAMP)
        self.assertRegex(end, SRT_TIMESTAMP)


class TestSplitStringByPunctuations(unittest.TestCase):
    """Sentence splitting for subtitle/script matching.

    Numbers must survive intact: if "2.5" or "1,000" is split, the script no
    longer lines up with the TTS boundaries and subtitle matching falls back
    to Whisper.
    """

    def test_splits_on_sentence_punctuation(self):
        self.assertEqual(
            utils.split_string_by_punctuations("Hello world. Goodbye now!"),
            ["Hello world", "Goodbye now"],
        )

    def test_decimal_point_between_digits_is_not_a_split(self):
        self.assertEqual(
            utils.split_string_by_punctuations("charged at 2.5% fee"),
            ["charged at 2.5% fee"],
        )

    def test_thousands_separator_between_digits_is_not_a_split(self):
        self.assertEqual(
            utils.split_string_by_punctuations("Withdraw 10,000, charged at 2.5% fee."),
            ["Withdraw 10,000", "charged at 2.5% fee"],
        )

    def test_newlines_split_lines(self):
        self.assertEqual(
            utils.split_string_by_punctuations("first\nsecond"), ["first", "second"]
        )

    def test_empty_segments_are_dropped(self):
        self.assertEqual(utils.split_string_by_punctuations("a..b"), ["a", "b"])
        self.assertEqual(utils.split_string_by_punctuations("   "), [])


class TestNormalizeScriptForSubtitleMatching(unittest.TestCase):
    """Markdown that TTS never speaks must not become a script line, or the
    matcher pads the SRT with 00:00:00,000 --> 00:00:00,000 blocks."""

    def test_markdown_separator_lines_are_removed(self):
        for separator in ("---", "***", "-----"):
            with self.subTest(separator=separator):
                self.assertEqual(
                    utils.normalize_script_for_subtitle_matching(
                        f"One\n{separator}\nTwo"
                    ),
                    "One\nTwo",
                )

    def test_underscore_separator_collapses_to_a_blank_line(self):
        # Underscores are stripped before the separator regex runs, so "___"
        # becomes "" rather than matching [-*_]{3,}. Documented because the
        # docstring lists "___" as a separator: the line is blanked, not
        # dropped, and only disappears once split_string_by_punctuations
        # filters empty segments.
        self.assertEqual(
            utils.normalize_script_for_subtitle_matching("One\n___\nTwo"),
            "One\n\nTwo",
        )

    def test_no_separator_style_survives_as_a_spoken_script_line(self):
        # This is the contract that actually matters: subtitle.correct() feeds
        # normalize() straight into split_string_by_punctuations().
        for separator in ("---", "***", "___", "-----"):
            with self.subTest(separator=separator):
                normalized = utils.normalize_script_for_subtitle_matching(
                    f"One\n{separator}\nTwo"
                )
                self.assertEqual(
                    utils.split_string_by_punctuations(normalized), ["One", "Two"]
                )

    def test_underscores_are_stripped_from_text(self):
        self.assertEqual(
            utils.normalize_script_for_subtitle_matching("Two_three"), "Twothree"
        )

    def test_lines_are_trimmed(self):
        self.assertEqual(
            utils.normalize_script_for_subtitle_matching("  One  \n  Two  "),
            "One\nTwo",
        )

    def test_none_and_empty_input_are_safe(self):
        self.assertEqual(utils.normalize_script_for_subtitle_matching(None), "")
        self.assertEqual(utils.normalize_script_for_subtitle_matching(""), "")

    def test_short_dashes_are_kept(self):
        # only runs of 3+ are separators; "--" can be legitimate punctuation
        self.assertEqual(
            utils.normalize_script_for_subtitle_matching("One\n--\nTwo"), "One\n--\nTwo"
        )


class TestParseExtension(unittest.TestCase):
    def test_returns_lowercase_extension_without_the_dot(self):
        self.assertEqual(utils.parse_extension("Narration.MP3"), "mp3")
        self.assertEqual(utils.parse_extension("/a/b/clip.MP4"), "mp4")

    def test_returns_empty_string_when_there_is_no_extension(self):
        self.assertEqual(utils.parse_extension("README"), "")


if __name__ == "__main__":
    unittest.main()
