import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import cli
from app.models.schema import VideoAspect, VideoConcatMode, VideoTransitionMode
from app.services import material
from app.services import video as vd

I18N_DIR = Path(__file__).parent.parent.parent / "webui" / "i18n"


class TestEnumsAreStringBacked(unittest.TestCase):
    """All three inherit `str`, which is what lets them be compared to, and
    serialised as, plain strings across the API, CLI and config."""

    def test_members_are_strings(self):
        for enum_cls in (VideoAspect, VideoConcatMode, VideoTransitionMode):
            for member in enum_cls:
                with self.subTest(member=member):
                    self.assertIsInstance(member, str)
                    self.assertEqual(member, member.value)

    def test_values_are_unique_within_each_enum(self):
        for enum_cls in (VideoAspect, VideoConcatMode, VideoTransitionMode):
            values = [m.value for m in enum_cls]
            with self.subTest(enum=enum_cls.__name__):
                self.assertEqual(len(values), len(set(values)))

    def test_values_are_json_serialisable(self):
        # They travel in API request/response bodies.
        for enum_cls in (VideoAspect, VideoConcatMode, VideoTransitionMode):
            with self.subTest(enum=enum_cls.__name__):
                json.dumps([m.value for m in enum_cls])


class TestPlainStringTolerance(unittest.TestCase):
    """Three call sites read the mode with `getattr(x, "value", x)` so a caller
    may pass either the enum or its raw string. API bodies deserialise to the
    enum; direct/service-level callers and tests pass the string."""

    def test_concat_mode_is_read_the_same_either_way(self):
        for member in VideoConcatMode:
            with self.subTest(member=member):
                self.assertEqual(
                    getattr(member, "value", member),
                    getattr(member.value, "value", member.value),
                )

    def test_prioritize_accepts_enum_and_string_alike(self):
        clips = [
            vd.SubClippedVideoClip(file_path="a#0", duration=5, source_file_path="a"),
            vd.SubClippedVideoClip(file_path="b#0", duration=4, source_file_path="b"),
        ]

        from_enum = vd._prioritize_unique_source_clips(clips, VideoConcatMode.sequential)
        from_string = vd._prioritize_unique_source_clips(clips, "sequential")

        self.assertEqual(len(from_enum), len(from_string))

    def test_download_videos_accepts_a_plain_string_mode(self):
        # Regression guard: this used to raise AttributeError on `.value`.
        result = material.download_videos(
            task_id="enum-contract", search_terms=[], video_concat_mode="random"
        )

        self.assertEqual(result, [])


class TestCrossComponentEnumAgreement(unittest.TestCase):
    """The same modes are spelled in four places — schema, CLI, WebUI labels and
    config.example.toml. Drift between them is a silent mismatch: the user picks
    a mode that the pipeline then fails to recognise."""

    def test_cli_transition_map_only_targets_real_enum_values(self):
        valid = {m.value for m in VideoTransitionMode}

        for mapped in cli._TRANSITION_MODE_VALUES.values():
            with self.subTest(mapped=mapped):
                if mapped is not None:
                    self.assertIn(mapped, valid)

    def test_cli_covers_every_transition_mode(self):
        mapped = {v for v in cli._TRANSITION_MODE_VALUES.values() if v is not None}
        expected = {m.value for m in VideoTransitionMode if m.value != "None"}

        self.assertEqual(mapped, expected)

    def test_every_transition_mode_has_an_english_label(self):
        translations = json.loads(
            (I18N_DIR / "en.json").read_text(encoding="utf-8")
        )["Translation"]

        for member in VideoTransitionMode:
            if member.value == "None":
                continue
            with self.subTest(member=member):
                self.assertIn(member.value, translations)

    def test_aspect_ratios_offered_by_the_webui_have_english_labels(self):
        translations = json.loads(
            (I18N_DIR / "en.json").read_text(encoding="utf-8")
        )["Translation"]

        # webui/Main.py builds its selectbox from Portrait + Landscape only.
        for name in ("Portrait", "Landscape"):
            with self.subTest(name=name):
                self.assertIn(name, translations)

    def test_square_is_an_api_only_aspect(self):
        """Documents that VideoAspect.square has no WebUI option.

        It is a valid `video_aspect` for POST /api/v1/videos and resolves
        correctly, but the WebUI offers only Portrait and Landscape and
        there is no "Square" i18n key. Pinned so the absence reads as a
        deliberate UI choice rather than a missing translation.
        """
        translations = json.loads(
            (I18N_DIR / "en.json").read_text(encoding="utf-8")
        )["Translation"]

        self.assertEqual(VideoAspect.square.to_resolution(), (1080, 1080))
        self.assertNotIn("Square", translations)

    def test_aspect_resolutions_are_consistent_with_their_ratios(self):
        for member in VideoAspect:
            width, height = member.to_resolution()
            ratio_w, ratio_h = (int(part) for part in member.value.split(":"))
            with self.subTest(member=member):
                self.assertAlmostEqual(width / height, ratio_w / ratio_h, places=2)


if __name__ == "__main__":
    unittest.main()
