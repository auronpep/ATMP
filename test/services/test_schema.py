import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pydantic import ValidationError

from app.models.schema import VideoAspect, VideoParams


class TestVideoAspect(unittest.TestCase):
    def test_to_resolution_known_aspects(self):
        self.assertEqual(VideoAspect.landscape.to_resolution(), (1920, 1080))
        self.assertEqual(VideoAspect.portrait.to_resolution(), (1080, 1920))
        self.assertEqual(VideoAspect.square.to_resolution(), (1080, 1080))

    def test_to_resolution_rejects_unsupported_value(self):
        with self.assertRaises(ValueError):
            VideoAspect.to_resolution("4:5")


if __name__ == "__main__":
    unittest.main()


class TestVideoParamsNumericBounds(unittest.TestCase):
    """`POST /api/v1/videos` binds straight to these models, and the auth
    dependency ships commented out, so out-of-range numbers reached the render
    pipeline and failed confusingly instead of returning 400."""

    def test_rejects_non_positive_counts_and_sizes(self):
        for field in ("video_count", "video_clip_duration", "n_threads", "font_size"):
            for value in (0, -3):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValidationError):
                        VideoParams(video_subject="x", **{field: value})

    def test_rejects_negative_volumes_and_stroke_width(self):
        for field in ("voice_volume", "bgm_volume", "stroke_width"):
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    VideoParams(video_subject="x", **{field: -1.0})

    def test_custom_position_is_a_percentage(self):
        for value in (-0.1, 100.1, 999.0):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    VideoParams(video_subject="x", custom_position=value)

        # cli.py::_percent_position and the WebUI both accept the full 0-100 range
        self.assertEqual(VideoParams(video_subject="x", custom_position=0).custom_position, 0)
        self.assertEqual(VideoParams(video_subject="x", custom_position=100).custom_position, 100)

    def test_defaults_are_unchanged(self):
        params = VideoParams(video_subject="x")

        self.assertEqual(params.video_count, 1)
        self.assertEqual(params.video_clip_duration, 5)
        self.assertEqual(params.n_threads, 2)
        self.assertEqual(params.font_size, 60)
        self.assertEqual(params.voice_volume, 1.0)
        self.assertEqual(params.bgm_volume, 0.2)
        self.assertEqual(params.stroke_width, 1.5)

    def test_zero_is_still_valid_where_it_is_meaningful(self):
        self.assertEqual(VideoParams(video_subject="x", bgm_volume=0).bgm_volume, 0)
        self.assertEqual(VideoParams(video_subject="x", voice_volume=0).voice_volume, 0)
        self.assertEqual(VideoParams(video_subject="x", stroke_width=0).stroke_width, 0)
