import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models.schema import VideoConcatMode
from app.services import video as vd
from app.services.video import SubClippedVideoClip


def _clip(source, duration, index=0):
    return SubClippedVideoClip(
        file_path=f"{source}#{index}",
        duration=duration,
        source_file_path=source,
        width=1080,
        height=1920,
    )


class TestRequiredVideoDuration(unittest.TestCase):
    """Material must out-run the narration.

    Matching the audio length exactly is not enough: the docstring notes that
    frame-rate rounding in FFmpeg can leave the final video marginally short,
    which cuts off the end of the voiceover. Hence a fixed safety margin.
    """

    def test_adds_the_safety_margin(self):
        self.assertAlmostEqual(
            vd._get_required_video_duration(10.0),
            10.0 + vd._VIDEO_DURATION_SAFETY_MARGIN,
        )

    def test_result_always_exceeds_the_audio_duration(self):
        for audio in (0.5, 1.0, 12.34, 300.0):
            with self.subTest(audio=audio):
                self.assertGreater(vd._get_required_video_duration(audio), audio)

    def test_never_returns_a_negative_duration(self):
        for audio in (0, -1, -100.5):
            with self.subTest(audio=audio):
                self.assertGreaterEqual(vd._get_required_video_duration(audio), 0.0)

    def test_accepts_numeric_strings(self):
        self.assertAlmostEqual(
            vd._get_required_video_duration("10"),
            10.0 + vd._VIDEO_DURATION_SAFETY_MARGIN,
        )


class TestPrioritizeUniqueSourceClips(unittest.TestCase):
    """Stock providers often return one long video sliced into several clips.

    Shuffling all slices together makes the same source reappear throughout the
    render, which viewers read as repetition. This puts one clip per source
    first, keeping the rest as fallback so a short material pool can still fill
    the timeline.
    """

    def setUp(self):
        random.seed(1234)

    def test_sequential_mode_is_left_untouched(self):
        items = [_clip("a", 5), _clip("a", 3), _clip("b", 4)]

        result = vd._prioritize_unique_source_clips(items, VideoConcatMode.sequential)

        self.assertIs(result, items)

    def test_empty_input_returns_empty(self):
        self.assertEqual(vd._prioritize_unique_source_clips([], VideoConcatMode.random), [])

    def test_no_clip_is_lost_or_duplicated(self):
        items = [_clip("a", 5, 0), _clip("a", 3, 1), _clip("b", 4, 0), _clip("c", 2, 0)]

        result = vd._prioritize_unique_source_clips(items, VideoConcatMode.random)

        self.assertEqual(len(result), len(items))
        self.assertEqual({id(i) for i in result}, {id(i) for i in items})

    def test_each_source_appears_once_before_any_source_repeats(self):
        items = [
            _clip("a", 5, 0), _clip("a", 4, 1), _clip("a", 3, 2),
            _clip("b", 6, 0), _clip("b", 1, 1),
            _clip("c", 2, 0),
        ]

        result = vd._prioritize_unique_source_clips(items, VideoConcatMode.random)
        leading = [c.source_file_path for c in result[:3]]

        self.assertEqual(sorted(leading), ["a", "b", "c"])

    def test_the_longest_clip_of_each_source_leads(self):
        # Picking a short tail slice would exhaust the pool early and force
        # reuse while good material was still available.
        items = [
            _clip("a", 1, 0), _clip("a", 9, 1),
            _clip("b", 2, 0), _clip("b", 7, 1),
        ]

        result = vd._prioritize_unique_source_clips(items, VideoConcatMode.random)
        leading = {c.source_file_path: c.duration for c in result[:2]}

        self.assertEqual(leading, {"a": 9, "b": 7})

    def test_a_single_source_still_returns_all_its_clips(self):
        items = [_clip("a", 5, 0), _clip("a", 3, 1), _clip("a", 1, 2)]

        result = vd._prioritize_unique_source_clips(items, VideoConcatMode.random)

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].duration, 5)

    def test_plain_string_concat_mode_is_accepted(self):
        # API callers may pass the raw enum value rather than the enum.
        items = [_clip("a", 5), _clip("b", 4)]

        result = vd._prioritize_unique_source_clips(items, "random")

        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
