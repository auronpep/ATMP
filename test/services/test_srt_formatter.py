import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services import voice as vs

SRT_BLOCK = re.compile(
    r"^\d+\n\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}\n.+\n$"
)
HNS = 10_000_000  # edge_tts uses 100-nanosecond units


class TestMktimestamp(unittest.TestCase):
    """edge_tts 7.x dropped its own `mktimestamp`, so this reimplements the
    100ns -> timestamp conversion the Azure v2, Gemini and SiliconFlow paths
    still build their timelines from."""

    def test_zero(self):
        self.assertEqual(vs.mktimestamp(0), "00:00:00.000")

    def test_seconds(self):
        self.assertEqual(vs.mktimestamp(1 * HNS), "00:00:01.000")
        self.assertEqual(vs.mktimestamp(int(1.5 * HNS)), "00:00:01.500")

    def test_minute_and_hour_rollover(self):
        self.assertEqual(vs.mktimestamp(60 * HNS), "00:01:00.000")
        self.assertEqual(vs.mktimestamp(3600 * HNS), "01:00:00.000")
        self.assertEqual(vs.mktimestamp(int((3600 + 120 + 3.5) * HNS)), "01:02:03.500")

    def test_components_are_zero_padded(self):
        for units in (0, 5 * HNS, 65 * HNS, 3605 * HNS):
            with self.subTest(units=units):
                self.assertRegex(vs.mktimestamp(units), r"^\d{2}:\d{2}:\d{2}\.\d{3}$")

    def test_seconds_never_reach_sixty(self):
        for units in (int(59.9999 * HNS), int(119.9999 * HNS)):
            with self.subTest(units=units):
                seconds = float(vs.mktimestamp(units).split(":")[2])
                self.assertLess(seconds, 60.0)


    def test_boundary_values_carry_into_the_minute(self):
        # 59.9999s must become 00:01:00.000, not the invalid 00:00:60.000.
        self.assertEqual(vs.mktimestamp(int(59.9999 * HNS)), "00:01:00.000")
        self.assertEqual(vs.mktimestamp(int(119.9999 * HNS)), "00:02:00.000")
        self.assertEqual(vs.mktimestamp(int(3599.9999 * HNS)), "01:00:00.000")

    def test_no_field_ever_exceeds_its_range(self):
        # Scan a whole minute at 100us resolution; an SRT reader rejects
        # the entire file on a single malformed stamp.
        for units in range(0, 60 * HNS, 1000):
            stamp = vs.mktimestamp(units)
            hours, minutes, rest = stamp.split(":")
            seconds = rest.split(".")[0]
            if int(minutes) >= 60 or int(seconds) >= 60:
                self.fail(f"invalid timestamp {stamp} for {units}")


class TestSubtitleFormatter(unittest.TestCase):
    """One formatter shared by the edge-tts cues path and the legacy
    subs/offset path, so the two cannot drift into slightly different SRT
    output — which is the stated reason it exists."""

    def setUp(self):
        self.format = vs._build_subtitle_formatter()

    def test_emits_a_well_formed_srt_block(self):
        block = self.format(idx=1, start_time=0, end_time=int(1.5 * HNS), sub_text="Hello")

        self.assertRegex(block, SRT_BLOCK)

    def test_uses_a_comma_decimal_separator(self):
        # SRT requires HH:MM:SS,mmm - a dot makes the file unimportable.
        block = self.format(idx=1, start_time=0, end_time=HNS, sub_text="Hello")

        self.assertIn("00:00:00,000 --> 00:00:01,000", block)
        self.assertNotIn(".", block.splitlines()[1])

    def test_index_and_text_are_placed_on_their_own_lines(self):
        lines = self.format(
            idx=7, start_time=0, end_time=HNS, sub_text="Hello world"
        ).splitlines()

        self.assertEqual(lines[0], "7")
        self.assertIn(" --> ", lines[1])
        self.assertEqual(lines[2], "Hello world")

    def test_non_ascii_text_is_preserved(self):
        block = self.format(idx=1, start_time=0, end_time=HNS, sub_text="金钱是一种工具")

        self.assertIn("金钱是一种工具", block)

    def test_consecutive_blocks_join_into_a_parseable_file(self):
        import tempfile

        blocks = [
            self.format(idx=i + 1, start_time=i * HNS, end_time=(i + 1) * HNS, sub_text=t)
            for i, t in enumerate(["First line", "Second line"])
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "sub.srt"
            path.write_text("\n".join(blocks) + "\n", encoding="utf-8")

            from app.services import subtitle

            items = subtitle.file_to_subtitles(str(path))

        self.assertEqual([i[2] for i in items], ["First line", "Second line"])


class TestFormatText(unittest.TestCase):
    """Strips markup TTS never speaks, so subtitle alignment doesn't wait on a
    cue that will never arrive."""

    def test_brackets_and_braces_become_spaces(self):
        result = vs._format_text("Hello [aside] (note) {tag} world")

        for ch in "[](){}":
            with self.subTest(ch=ch):
                self.assertNotIn(ch, result)

    def test_spoken_words_survive(self):
        result = vs._format_text("Hello [aside] world")

        self.assertIn("Hello", result)
        self.assertIn("world", result)

    def test_markdown_separators_are_removed(self):
        self.assertNotIn("---", vs._format_text("One\n---\nTwo"))

    def test_plain_text_is_effectively_unchanged(self):
        self.assertEqual(vs._format_text("Hello world"), "Hello world")


if __name__ == "__main__":
    unittest.main()
