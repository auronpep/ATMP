import argparse
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import cli


class TestPositiveInt(unittest.TestCase):
    """Backs --video-count, --video-clip-duration, --n-threads, --font-size."""

    def test_accepts_positive_values(self):
        self.assertEqual(cli._positive_int("1"), 1)
        self.assertEqual(cli._positive_int("42"), 42)

    def test_rejects_zero_and_negatives(self):
        for value in ("0", "-1", "-99"):
            with self.subTest(value=value):
                with self.assertRaises(argparse.ArgumentTypeError):
                    cli._positive_int(value)

    def test_rejects_non_numeric(self):
        for value in ("abc", "", "1.5"):
            with self.subTest(value=value):
                with self.assertRaises((argparse.ArgumentTypeError, ValueError)):
                    cli._positive_int(value)


class TestParagraphCount(unittest.TestCase):
    """Mirrors llm.MIN/MAX_SCRIPT_PARAGRAPH_NUMBER."""

    def test_accepts_the_documented_range(self):
        for value in range(1, 11):
            with self.subTest(value=value):
                self.assertEqual(cli._paragraph_count(str(value)), value)

    def test_rejects_outside_the_range(self):
        for value in ("0", "11", "-1", "100"):
            with self.subTest(value=value):
                with self.assertRaises(argparse.ArgumentTypeError):
                    cli._paragraph_count(value)

    def test_bounds_match_the_llm_module(self):
        from app.services import llm

        self.assertEqual(cli._paragraph_count(str(llm.MIN_SCRIPT_PARAGRAPH_NUMBER)),
                         llm.MIN_SCRIPT_PARAGRAPH_NUMBER)
        self.assertEqual(cli._paragraph_count(str(llm.MAX_SCRIPT_PARAGRAPH_NUMBER)),
                         llm.MAX_SCRIPT_PARAGRAPH_NUMBER)


class TestNonNegativeFloat(unittest.TestCase):
    """Backs the volume and stroke-width flags."""

    def test_accepts_zero_and_positives(self):
        self.assertEqual(cli._non_negative_float("0"), 0.0)
        self.assertEqual(cli._non_negative_float("1.5"), 1.5)

    def test_rejects_negatives(self):
        for value in ("-0.1", "-5"):
            with self.subTest(value=value):
                with self.assertRaises(argparse.ArgumentTypeError):
                    cli._non_negative_float(value)


class TestPercentPosition(unittest.TestCase):
    """--custom-position is a percentage from the top of the frame."""

    def test_accepts_the_inclusive_range(self):
        for value in ("0", "50.5", "100"):
            with self.subTest(value=value):
                self.assertEqual(cli._percent_position(value), float(value))

    def test_rejects_outside_zero_to_one_hundred(self):
        for value in ("-0.1", "100.1", "999"):
            with self.subTest(value=value):
                with self.assertRaises(argparse.ArgumentTypeError):
                    cli._percent_position(value)


class TestHexColor(unittest.TestCase):
    """Colours are passed to MoviePy/PIL; a malformed value fails deep in
    rendering rather than at the command line."""

    def test_accepts_six_digit_hex_in_either_case(self):
        for value in ("#FFFFFF", "#000000", "#a1b2c3", "#A1B2C3"):
            with self.subTest(value=value):
                self.assertEqual(cli._hex_color(value), value)

    def test_rejects_malformed_colours(self):
        for value in ("FFFFFF", "#FFF", "#GGGGGG", "#FFFFFFF", "white", ""):
            with self.subTest(value=value):
                with self.assertRaises(argparse.ArgumentTypeError):
                    cli._hex_color(value)


class TestTransitionMode(unittest.TestCase):
    """CLI spelling maps to the VideoTransitionMode enum values."""

    def test_maps_cli_spelling_to_enum_values(self):
        self.assertIsNone(cli._transition_mode("none"))
        self.assertEqual(cli._transition_mode("fade-in"), "FadeIn")
        self.assertEqual(cli._transition_mode("fade-out"), "FadeOut")
        self.assertEqual(cli._transition_mode("slide-in"), "SlideIn")
        self.assertEqual(cli._transition_mode("slide-out"), "SlideOut")
        self.assertEqual(cli._transition_mode("shuffle"), "Shuffle")

    def test_is_case_and_whitespace_insensitive(self):
        self.assertEqual(cli._transition_mode("  FADE-IN  "), "FadeIn")

    def test_rejects_unknown_modes(self):
        for value in ("fadein", "wipe", ""):
            with self.subTest(value=value):
                with self.assertRaises(argparse.ArgumentTypeError):
                    cli._transition_mode(value)

    def test_every_mapped_value_is_a_real_enum_member(self):
        from app.models.schema import VideoTransitionMode

        valid = {m.value for m in VideoTransitionMode}
        for mapped in cli._TRANSITION_MODE_VALUES.values():
            with self.subTest(mapped=mapped):
                if mapped is not None:
                    self.assertIn(mapped, valid)


class TestBgmType(unittest.TestCase):
    def test_none_disables_background_music(self):
        self.assertEqual(cli._bgm_type("none"), "")

    def test_accepts_random_and_custom(self):
        self.assertEqual(cli._bgm_type("random"), "random")
        self.assertEqual(cli._bgm_type("custom"), "custom")

    def test_is_case_and_whitespace_insensitive(self):
        self.assertEqual(cli._bgm_type("  RANDOM  "), "random")

    def test_rejects_unknown_values(self):
        for value in ("silent", "mp3"):
            with self.subTest(value=value):
                with self.assertRaises(argparse.ArgumentTypeError):
                    cli._bgm_type(value)


if __name__ == "__main__":
    unittest.main()
