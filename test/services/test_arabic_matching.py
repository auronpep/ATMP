import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services import voice as vs


class TestNormalizeArabic(unittest.TestCase):
    """edge-tts can return Arabic in a different letter form than the script it
    was given. This normaliser is the last-chance layer that still lets a cue
    match its script line; without it the subtitle pipeline falls through to a
    Whisper re-transcription of audio it already has timings for."""

    def test_hamza_forms_fold_to_plain_alef(self):
        for variant in ("أ", "إ", "آ", "ٱ"):
            with self.subTest(variant=variant):
                self.assertEqual(vs._normalize_arabic(variant), "ا")

    def test_alef_maqsura_and_yeh_hamza_fold_to_yeh(self):
        for variant in ("ى", "ئ"):
            with self.subTest(variant=variant):
                self.assertEqual(vs._normalize_arabic(variant), "ي")

    def test_teh_marbuta_folds_to_heh(self):
        self.assertEqual(vs._normalize_arabic("ة"), "ه")

    def test_waw_hamza_folds_to_waw(self):
        self.assertEqual(vs._normalize_arabic("ؤ"), "و")

    def test_diacritics_are_stripped(self):
        # "مَرْحَبًا" (with harakat) must reduce to the bare consonant skeleton.
        self.assertEqual(vs._normalize_arabic("مَرْحَبًا"), "مرحبا")

    def test_plain_text_is_unchanged(self):
        for text in ("hello world", "你好", "", "123"):
            with self.subTest(text=text):
                self.assertEqual(vs._normalize_arabic(text), text)

    def test_normalisation_is_idempotent(self):
        once = vs._normalize_arabic("أهلاً وسهلاً")
        self.assertEqual(vs._normalize_arabic(once), once)


class TestMatchScriptLine(unittest.TestCase):
    """Aligns the accumulated cue text against the next script line."""

    def test_exact_match(self):
        self.assertEqual(
            vs._match_script_line(["hello world", "second"], "hello world", 0),
            "hello world",
        )

    def test_punctuation_and_underscore_differences_are_tolerated(self):
        # TTS boundaries often drop or split punctuation.
        self.assertEqual(
            vs._match_script_line(["hello, world!"], "hello world", 0), "hello, world!"
        )
        self.assertEqual(
            vs._match_script_line(["hello _world_"], "hello world", 0), "hello _world_"
        )

    def test_arabic_letter_variants_are_tolerated(self):
        script = ["أهلا بالعالم"]
        cue = "اهلا بالعالم"  # hamza folded by the TTS engine

        self.assertEqual(vs._match_script_line(script, cue, 0), "أهلا بالعالم")

    def test_non_matching_text_returns_empty(self):
        self.assertEqual(vs._match_script_line(["hello world"], "goodbye", 0), "")

    def test_index_beyond_the_script_returns_empty(self):
        self.assertEqual(vs._match_script_line(["only line"], "only line", 5), "")
        self.assertEqual(vs._match_script_line([], "anything", 0), "")

    def test_result_is_the_script_line_not_the_cue(self):
        # The script wording is authoritative for what gets written to the SRT.
        self.assertEqual(
            vs._match_script_line(["Hello, World!"], "Hello World", 0), "Hello, World!"
        )

    def test_empty_cue_does_not_match_an_arbitrary_line(self):
        self.assertEqual(vs._match_script_line(["hello"], "", 0), "")


if __name__ == "__main__":
    unittest.main()
