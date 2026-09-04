import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services import subtitle


def _srt(blocks):
    out = []
    for idx, (span, text) in enumerate(blocks, start=1):
        out.append(f"{idx}\n{span}\n{text}\n")
    return "\n".join(out)


class TestCorrect(unittest.TestCase):
    """Realigns a Whisper transcript against the script the user actually wrote.

    Whisper splits sentences differently and mishears words, so `correct()`
    merges adjacent cues until they resemble a script line, then rewrites the
    text to the script's wording while keeping Whisper's timings. Getting this
    wrong produces captions that are subtly not what was said.
    """

    def _correct(self, blocks, script):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "sub.srt"
            path.write_text(_srt(blocks), encoding="utf-8")

            subtitle.correct(str(path), script)

            return subtitle.file_to_subtitles(str(path))

    def test_matching_subtitles_are_left_alone(self):
        blocks = [
            ("00:00:00,000 --> 00:00:01,000", "Hello world"),
            ("00:00:01,000 --> 00:00:02,000", "Goodbye now"),
        ]

        items = self._correct(blocks, "Hello world. Goodbye now.")

        self.assertEqual([i[2] for i in items], ["Hello world", "Goodbye now"])

    def test_split_cues_are_merged_back_into_one_script_line(self):
        # Whisper often breaks a sentence across cues.
        blocks = [
            ("00:00:00,000 --> 00:00:00,500", "Hello"),
            ("00:00:00,500 --> 00:00:01,000", "world"),
        ]

        items = self._correct(blocks, "Hello world.")

        self.assertEqual([i[2] for i in items], ["Hello world"])

    def test_merged_block_spans_the_full_time_range(self):
        blocks = [
            ("00:00:00,000 --> 00:00:00,500", "Hello"),
            ("00:00:00,500 --> 00:00:02,250", "world"),
        ]

        items = self._correct(blocks, "Hello world.")

        self.assertEqual(items[0][1], "00:00:00,000 --> 00:00:02,250")

    def test_a_misheard_word_is_rewritten_to_the_script_wording(self):
        blocks = [("00:00:00,000 --> 00:00:01,000", "Hello worla")]

        items = self._correct(blocks, "Hello world.")

        self.assertEqual([i[2] for i in items], ["Hello world"])

    def test_timings_are_preserved_when_text_is_corrected(self):
        blocks = [("00:00:03,250 --> 00:00:04,750", "Hello worla")]

        items = self._correct(blocks, "Hello world.")

        self.assertEqual(items[0][1], "00:00:03,250 --> 00:00:04,750")

    def test_blocks_are_renumbered_sequentially(self):
        blocks = [
            ("00:00:00,000 --> 00:00:00,500", "Hello"),
            ("00:00:00,500 --> 00:00:01,000", "world"),
            ("00:00:01,000 --> 00:00:02,000", "Goodbye now"),
        ]

        items = self._correct(blocks, "Hello world. Goodbye now.")

        self.assertEqual([i[0] for i in items], list(range(1, len(items) + 1)))

    def test_extra_script_lines_are_appended(self):
        blocks = [("00:00:00,000 --> 00:00:01,000", "Hello world")]

        items = self._correct(blocks, "Hello world. Goodbye now.")

        self.assertEqual([i[2] for i in items], ["Hello world", "Goodbye now"])

    def test_markdown_separator_lines_never_become_subtitles(self):
        blocks = [
            ("00:00:00,000 --> 00:00:01,000", "Hello world"),
            ("00:00:01,000 --> 00:00:02,000", "Goodbye now"),
        ]

        items = self._correct(blocks, "Hello world.\n---\nGoodbye now.")

        self.assertEqual([i[2] for i in items], ["Hello world", "Goodbye now"])
        self.assertNotIn("---", "".join(i[2] for i in items))

    def test_output_remains_parseable(self):
        blocks = [
            ("00:00:00,000 --> 00:00:00,500", "Hello"),
            ("00:00:00,500 --> 00:00:01,000", "worla"),
        ]

        items = self._correct(blocks, "Hello world.")

        for index, span, text in items:
            with self.subTest(index=index):
                self.assertIn(" --> ", span)
                self.assertTrue(text)

    def test_an_already_correct_file_is_not_rewritten(self):
        blocks = [("00:00:00,000 --> 00:00:01,000", "Hello world")]

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "sub.srt"
            original = _srt(blocks)
            path.write_text(original, encoding="utf-8")

            subtitle.correct(str(path), "Hello world.")

            self.assertEqual(path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
