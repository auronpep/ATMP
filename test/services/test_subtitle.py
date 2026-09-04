import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

# 测试文件直接运行时，也能从仓库根目录导入 app 包。
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services import subtitle


class TestSubtitleService(unittest.TestCase):
    def test_correct_ignores_markdown_separator_lines(self):
        """
        Whisper fallback 校正阶段也必须忽略 `---` 这类不可发声脚本行。

        如果这里继续保留 Markdown 分隔符，`correct()` 会认为脚本行数多于
        字幕行数，并补出 `00:00:00,000 --> 00:00:00,000`，剪辑软件会把
        生成的 SRT 判定为不可导入。
        """
        original_srt = (
            "1\n"
            "00:00:00,100 --> 00:00:01,000\n"
            "第一段\n\n"
            "2\n"
            "00:00:01,100 --> 00:00:02,000\n"
            "第二段\n\n"
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            subtitle_file = Path(tmp_dir) / "subtitle.srt"
            subtitle_file.write_text(original_srt, encoding="utf-8")

            subtitle.correct(
                subtitle_file=str(subtitle_file),
                video_script="第一段\n---\n第二段",
            )

            corrected_srt = subtitle_file.read_text(encoding="utf-8")

        self.assertIn("第一段", corrected_srt)
        self.assertIn("第二段", corrected_srt)
        self.assertNotIn("---", corrected_srt)
        self.assertNotIn("00:00:00,000 --> 00:00:00,000", corrected_srt)

    def test_file_to_subtitles_keeps_last_block_without_trailing_newline(self):
        """
        The final subtitle must be parsed even when the SRT file does not end
        with a trailing blank line. Many tools omit it, and previously the last
        block was silently dropped because only a blank line flushed a block.
        """
        srt_without_trailing_blank = (
            "1\n"
            "00:00:00,000 --> 00:00:01,000\n"
            "Hello\n\n"
            "2\n"
            "00:00:01,000 --> 00:00:02,000\n"
            "World"
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            subtitle_file = Path(tmp_dir) / "subtitle.srt"
            subtitle_file.write_text(srt_without_trailing_blank, encoding="utf-8")

            items = subtitle.file_to_subtitles(str(subtitle_file))

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0][2], "Hello")
        self.assertEqual(items[1][2], "World")

    def test_file_to_subtitles_parses_blocks_with_trailing_newline(self):
        """A normal SRT ending in a blank line still parses all blocks."""
        srt_with_trailing_blank = (
            "1\n"
            "00:00:00,000 --> 00:00:01,000\n"
            "Hello\n\n"
            "2\n"
            "00:00:01,000 --> 00:00:02,000\n"
            "World\n\n"
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            subtitle_file = Path(tmp_dir) / "subtitle.srt"
            subtitle_file.write_text(srt_with_trailing_blank, encoding="utf-8")

            items = subtitle.file_to_subtitles(str(subtitle_file))

        self.assertEqual([item[2] for item in items], ["Hello", "World"])


class TestWhisperWordSegmentation(unittest.TestCase):
    """`create()` must only break a sentence on punctuation that ENDS a word.

    Whisper emits " 2.5" as one word. Matching the inner "." split the line
    mid-number and silently deleted the digit behind the dot.
    """

    def _transcribe(self, spoken_words):
        """Run create() against a fake model that emits `spoken_words`."""
        words = []
        for idx, text in enumerate(spoken_words):
            words.append(
                types.SimpleNamespace(word=text, start=float(idx), end=float(idx + 1))
            )
        segment = types.SimpleNamespace(
            words=words, start=0.0, end=float(len(words))
        )
        info = types.SimpleNamespace(language="en", language_probability=1.0)
        fake_model = types.SimpleNamespace(
            transcribe=lambda *args, **kwargs: ([segment], info)
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            subtitle_file = Path(tmp_dir) / "out.srt"
            with patch.object(subtitle, "model", fake_model):
                subtitle.create("audio.mp3", str(subtitle_file))
            return [item[2] for item in subtitle.file_to_subtitles(str(subtitle_file))]

    def test_decimal_number_is_not_split_and_keeps_its_digits(self):
        lines = self._transcribe(
            [" The", " price", " is", " 2.5", " percent", " today."]
        )

        self.assertEqual(lines, ["The price is 2.5 percent today"])

    def test_sentence_final_punctuation_still_breaks_the_line(self):
        lines = self._transcribe([" Hello", " world.", " Goodbye", " now."])

        self.assertEqual(lines, ["Hello world", "Goodbye now"])

    def test_abbreviation_inside_a_word_does_not_break_the_line(self):
        lines = self._transcribe([" Made", " in", " the", " U.S.A", " today."])

        self.assertEqual(lines, ["Made in the U.S.A today"])


if __name__ == "__main__":
    unittest.main()
