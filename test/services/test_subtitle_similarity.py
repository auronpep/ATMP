import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.subtitle import levenshtein_distance, similarity
from app.utils import utils


class TestLevenshteinDistance(unittest.TestCase):
    def test_identical_strings_have_zero_distance(self):
        self.assertEqual(levenshtein_distance("hello", "hello"), 0)

    def test_single_edits(self):
        self.assertEqual(levenshtein_distance("hello", "hallo"), 1)   # substitute
        self.assertEqual(levenshtein_distance("hello", "hell"), 1)    # delete
        self.assertEqual(levenshtein_distance("hell", "hello"), 1)    # insert

    def test_distance_is_symmetric(self):
        for a, b in (("kitten", "sitting"), ("abc", ""), ("", "xyz")):
            with self.subTest(a=a, b=b):
                self.assertEqual(levenshtein_distance(a, b), levenshtein_distance(b, a))

    def test_empty_against_text_is_the_text_length(self):
        self.assertEqual(levenshtein_distance("", "hello"), 5)
        self.assertEqual(levenshtein_distance("", ""), 0)

    def test_known_value(self):
        self.assertEqual(levenshtein_distance("kitten", "sitting"), 3)

    def test_handles_non_ascii(self):
        self.assertEqual(levenshtein_distance("金钱", "金钱"), 0)
        self.assertEqual(levenshtein_distance("金钱", "金币"), 1)


class TestSimilarity(unittest.TestCase):
    """`correct()` rewrites a Whisper subtitle line to the script wording when
    similarity > 0.8. Too low and correct text is left mangled; too high and
    unrelated lines get overwritten with the wrong script sentence."""

    def test_identical_text_scores_one(self):
        self.assertEqual(similarity("hello world", "hello world"), 1.0)

    def test_comparison_is_case_insensitive(self):
        self.assertEqual(similarity("Hello World", "hello world"), 1.0)

    def test_completely_different_text_scores_low(self):
        self.assertLess(similarity("hello world", "xxxxxxxxxxx"), 0.3)

    def test_a_one_character_difference_stays_above_the_correction_threshold(self):
        # The 0.8 gate in correct() must still fire for near-misses, which is
        # what Whisper actually produces.
        self.assertGreater(similarity("hello world", "hello worla"), 0.8)

    def test_empty_against_text_scores_zero(self):
        self.assertEqual(similarity("abc", ""), 0.0)
        self.assertEqual(similarity("", "abc"), 0.0)

    def test_score_is_within_the_unit_interval(self):
        pairs = (
            ("hello", "hello"),
            ("hello", "hallo"),
            ("hello", "xyz"),
            ("hello", ""),
            ("金钱是一种社会工具", "金钱是一种社会工具"),
        )
        for a, b in pairs:
            with self.subTest(a=a, b=b):
                self.assertGreaterEqual(similarity(a, b), 0.0)
                self.assertLessEqual(similarity(a, b), 1.0)


class TestSimilarityEmptyPairIsUnreachable(unittest.TestCase):
    """`similarity("", "")` divides by zero.

    Documented rather than "fixed": the only callers are in `correct()`, and
    both pass a `script_line` that comes from
    `split_string_by_punctuations()`, which filters empty segments out. So the
    degenerate pair cannot occur on any current path. This test pins the
    property that actually protects it, so the guard is visible if that
    filtering ever changes.
    """

    def test_split_never_yields_an_empty_script_line(self):
        for text in ("", "   ", "...", "a..b", "hello. world.", "\n\n"):
            with self.subTest(text=text):
                self.assertTrue(
                    all(line for line in utils.split_string_by_punctuations(text))
                )

    def test_the_degenerate_pair_would_raise(self):
        with self.assertRaises(ZeroDivisionError):
            similarity("", "")


if __name__ == "__main__":
    unittest.main()
