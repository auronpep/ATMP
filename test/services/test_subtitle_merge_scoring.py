import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services import subtitle


def _srt(cues):
    return "".join(
        f"{i + 1}\n00:00:{i:02d},000 --> 00:00:{i:02d},500\n{text}\n\n"
        for i, text in enumerate(cues)
    )


class TestMergeScoringIsNotRecomputed(unittest.TestCase):
    """The merge loop compares 'current candidate' against 'candidate + next'.

    The current candidate's score was already computed on the previous
    iteration, as that iteration's merged candidate. Recomputing it doubles the
    number of O(n*m) Levenshtein passes for every cue merged.
    """

    def _run(self, cues, script):
        calls = {"n": 0}
        real = subtitle.similarity

        def counting(a, b):
            calls["n"] += 1
            return real(a, b)

        original = subtitle.similarity
        subtitle.similarity = counting
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                path = Path(tmp_dir) / "sub.srt"
                path.write_text(_srt(cues), encoding="utf-8")
                subtitle.correct(str(path), script)
                items = subtitle.file_to_subtitles(str(path))
        finally:
            subtitle.similarity = original
        return items, calls["n"]

    def test_similarity_is_called_once_per_merge_candidate(self):
        cues = [f"w{i}" for i in range(9)]
        script = " ".join(cues) + "."

        _, calls = self._run(cues, script)

        # One call to seed the running score, then one per candidate examined.
        self.assertLessEqual(
            calls, len(cues), f"similarity() called {calls}x for {len(cues)} cues"
        )

    def test_merging_still_produces_the_script_line(self):
        cues = ["Hello", "world"]

        items, _ = self._run(cues, "Hello world.")

        self.assertEqual([i[2] for i in items], ["Hello world"])

    def test_merging_still_spans_the_full_time_range(self):
        cues = ["Hello", "world"]

        items, _ = self._run(cues, "Hello world.")

        self.assertEqual(items[0][1], "00:00:00,000 --> 00:00:01,500")

    def test_merge_stops_when_adding_a_cue_stops_helping(self):
        # "Goodbye" belongs to the second script line and must not be merged in.
        cues = ["Hello", "world", "Goodbye"]

        items, _ = self._run(cues, "Hello world. Goodbye.")

        self.assertEqual([i[2] for i in items], ["Hello world", "Goodbye"])

    def test_single_cue_needs_no_merge_scan(self):
        items, _ = self._run(["Hello world"], "Hello world.")

        self.assertEqual([i[2] for i in items], ["Hello world"])


if __name__ == "__main__":
    unittest.main()
