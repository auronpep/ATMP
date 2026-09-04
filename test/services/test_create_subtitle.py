import sys
import tempfile
import types
import unittest
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services import voice as vs


def _cue(content, start, end):
    return types.SimpleNamespace(
        content=content, start=timedelta(seconds=start), end=timedelta(seconds=end)
    )


def _sub_maker(cues):
    return types.SimpleNamespace(cues=cues)


class TestCreateSubtitleFromEdgeCues(unittest.TestCase):
    """edge-tts is the default TTS provider, so this aggregation runs on almost
    every task. It folds word-level cues back into script sentences — without it
    Chinese captions render one word per line.

    When it cannot align, it writes nothing and `generate_subtitle()` falls back
    to a full Whisper re-transcription of audio whose timings were already
    known, so both the success and the give-up path matter.
    """

    def _create(self, cues, text):
        with tempfile.TemporaryDirectory() as tmp_dir:
            out = Path(tmp_dir) / "sub.srt"
            vs.create_subtitle(_sub_maker(cues), text, str(out))
            if not out.exists():
                return None
            return out.read_text(encoding="utf-8")

    def test_word_cues_are_aggregated_into_script_sentences(self):
        cues = [
            _cue("Hello ", 0.0, 0.5),
            _cue("world.", 0.5, 1.0),
            _cue("Goodbye ", 1.0, 1.5),
            _cue("now.", 1.5, 2.0),
        ]

        srt = self._create(cues, "Hello world. Goodbye now.")

        self.assertIsNotNone(srt, "no subtitle file written")
        self.assertIn("Hello world", srt)
        self.assertIn("Goodbye now", srt)

    def test_timeline_spans_first_cue_start_to_last_cue_end(self):
        cues = [_cue("Hello ", 0.25, 0.5), _cue("world.", 0.5, 1.75)]

        srt = self._create(cues, "Hello world.")

        self.assertIn("00:00:00,250", srt)
        self.assertIn("00:00:01,750", srt)

    def test_each_script_line_becomes_one_numbered_block(self):
        cues = [
            _cue("One.", 0.0, 1.0),
            _cue("Two.", 1.0, 2.0),
            _cue("Three.", 2.0, 3.0),
        ]

        srt = self._create(cues, "One. Two. Three.")

        self.assertIsNotNone(srt)
        self.assertIn("1\n", srt)
        self.assertIn("2\n", srt)
        self.assertIn("3\n", srt)

    def test_output_parses_as_srt(self):
        cues = [_cue("Hello ", 0.0, 0.5), _cue("world.", 0.5, 1.0)]

        with tempfile.TemporaryDirectory() as tmp_dir:
            out = Path(tmp_dir) / "sub.srt"
            vs.create_subtitle(_sub_maker(cues), "Hello world.", str(out))

            from app.services import subtitle

            items = subtitle.file_to_subtitles(str(out))

        self.assertEqual([i[2] for i in items], ["Hello world"])

    def test_unalignable_cues_write_no_file_rather_than_a_wrong_one(self):
        # A partial match must not produce an SRT that disagrees with the audio;
        # the caller falls back to Whisper instead.
        cues = [_cue("Completely ", 0.0, 0.5), _cue("different.", 0.5, 1.0)]

        self.assertIsNone(self._create(cues, "Hello world. Goodbye now."))

    def test_partially_aligned_cues_write_no_file(self):
        """The length guard's real job.

        Here the first script line aligns and the second does not. Writing
        anyway would produce a perfectly valid SRT that silently drops the
        second half of the narration - worse than no subtitles, because
        nothing downstream can tell it is incomplete.
        """
        cues = [
            _cue("Hello ", 0.0, 0.5),
            _cue("world.", 0.5, 1.0),
            _cue("Something ", 1.0, 1.5),
            _cue("unrelated.", 1.5, 2.0),
        ]

        self.assertIsNone(self._create(cues, "Hello world. Goodbye now."))

    def test_empty_cues_write_no_file(self):
        self.assertIsNone(self._create([], "Hello world."))

    def test_punctuation_differences_between_cues_and_script_still_align(self):
        # TTS boundaries routinely drop or relocate punctuation.
        cues = [_cue("Hello ", 0.0, 0.5), _cue("world", 0.5, 1.0)]

        srt = self._create(cues, "Hello world.")

        self.assertIsNotNone(srt)
        self.assertIn("Hello world", srt)

    def test_a_failure_inside_the_builder_is_swallowed_not_raised(self):
        broken = types.SimpleNamespace(cues=[types.SimpleNamespace()])  # no .content

        with tempfile.TemporaryDirectory() as tmp_dir:
            out = Path(tmp_dir) / "sub.srt"
            vs.create_subtitle(broken, "Hello world.", str(out))  # must not raise

            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
