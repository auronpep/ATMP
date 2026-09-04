import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from moviepy import ColorClip

from app.services.utils import video_effects

WIDTH, HEIGHT = 100, 50
DURATION = 2.0
TRANSITION = 1.0


def _clip():
    return ColorClip(size=(WIDTH, HEIGHT), color=(1, 2, 3)).with_duration(DURATION)


def _moving_layer(composite):
    """The slide transitions composite [black background, moving clip]."""
    return composite.clips[-1]


class TestSlideInTransition(unittest.TestCase):
    """The module replaced MoviePy's built-in SlideIn because it produced a
    transition that was "applied" but visually almost static. These tests assert
    the clip actually travels a full frame width/height."""

    def _positions(self, side, times):
        layer = _moving_layer(
            video_effects.slidein_transition(_clip(), TRANSITION, side)
        )
        return [layer.pos(t) for t in times]

    def test_starts_offscreen_and_lands_on_frame(self):
        expected = {
            "left": ((-WIDTH, 0), (0, 0)),
            "right": ((WIDTH, 0), (0, 0)),
            "top": ((0, -HEIGHT), (0, 0)),
            "bottom": ((0, HEIGHT), (0, 0)),
        }
        for side, (start, end) in expected.items():
            with self.subTest(side=side):
                got_start, got_end = self._positions(side, [0.0, TRANSITION])
                self.assertEqual(tuple(got_start), start)
                self.assertEqual(tuple(got_end), end)

    def test_moves_halfway_at_the_midpoint(self):
        self.assertEqual(
            tuple(self._positions("left", [TRANSITION / 2])[0]), (-WIDTH / 2, 0)
        )
        self.assertEqual(
            tuple(self._positions("top", [TRANSITION / 2])[0]), (0, -HEIGHT / 2)
        )

    def test_stays_on_frame_after_the_transition(self):
        self.assertEqual(tuple(self._positions("left", [DURATION])[0]), (0, 0))

    def test_unknown_side_is_a_no_op_rather_than_an_error(self):
        self.assertEqual(tuple(self._positions("diagonal", [0.0])[0]), (0, 0))

    def test_zero_duration_does_not_divide_by_zero(self):
        # `max(t, 0.001)` guards the division; a 0s transition snaps on frame
        # instead of raising.
        layer = _moving_layer(video_effects.slidein_transition(_clip(), 0, "left"))

        self.assertEqual(tuple(layer.pos(0.0)), (-WIDTH, 0))
        self.assertEqual(tuple(layer.pos(0.01)), (0, 0))

    def test_output_keeps_the_source_size_and_duration(self):
        result = video_effects.slidein_transition(_clip(), TRANSITION, "left")

        self.assertEqual(result.size, (WIDTH, HEIGHT))
        self.assertEqual(result.duration, DURATION)

    def test_a_background_layer_is_added_behind_the_clip(self):
        result = video_effects.slidein_transition(_clip(), TRANSITION, "left")

        # background + moving clip; without the background the incoming frame
        # would expose whatever was underneath.
        self.assertGreaterEqual(len(result.clips), 2)


class TestSlideOutTransition(unittest.TestCase):
    def _positions(self, side, times):
        layer = _moving_layer(
            video_effects.slideout_transition(_clip(), TRANSITION, side)
        )
        return [layer.pos(t) for t in times]

    def test_holds_still_until_the_transition_window(self):
        for side in ("left", "right", "top", "bottom"):
            with self.subTest(side=side):
                held = self._positions(side, [0.0, DURATION - TRANSITION])
                self.assertEqual([tuple(p) for p in held], [(0, 0), (0, 0)])

    def test_ends_fully_offscreen(self):
        expected = {
            "left": (-WIDTH, 0),
            "right": (WIDTH, 0),
            "top": (0, -HEIGHT),
            "bottom": (0, HEIGHT),
        }
        for side, end in expected.items():
            with self.subTest(side=side):
                self.assertEqual(tuple(self._positions(side, [DURATION])[0]), end)

    def test_moves_halfway_through_the_window(self):
        midpoint = DURATION - TRANSITION / 2
        self.assertEqual(
            tuple(self._positions("left", [midpoint])[0]), (-WIDTH / 2, 0)
        )

    def test_unknown_side_is_a_no_op_rather_than_an_error(self):
        self.assertEqual(tuple(self._positions("diagonal", [DURATION])[0]), (0, 0))

    def test_output_keeps_the_source_size_and_duration(self):
        result = video_effects.slideout_transition(_clip(), TRANSITION, "left")

        self.assertEqual(result.size, (WIDTH, HEIGHT))
        self.assertEqual(result.duration, DURATION)


class TestFadeTransitions(unittest.TestCase):
    def test_fadein_preserves_size_and_duration(self):
        result = video_effects.fadein_transition(_clip(), TRANSITION)

        self.assertEqual(result.size, (WIDTH, HEIGHT))
        self.assertEqual(result.duration, DURATION)

    def test_fadeout_preserves_size_and_duration(self):
        result = video_effects.fadeout_transition(_clip(), TRANSITION)

        self.assertEqual(result.size, (WIDTH, HEIGHT))
        self.assertEqual(result.duration, DURATION)

    def test_fadein_darkens_the_first_frame(self):
        source_first = _clip().get_frame(0).mean()
        faded_first = video_effects.fadein_transition(_clip(), TRANSITION).get_frame(0).mean()

        self.assertLess(faded_first, source_first)

    def test_fadeout_darkens_the_final_frame(self):
        source_last = _clip().get_frame(DURATION - 0.01).mean()
        faded_last = (
            video_effects.fadeout_transition(_clip(), TRANSITION)
            .get_frame(DURATION - 0.01)
            .mean()
        )

        self.assertLess(faded_last, source_last)


if __name__ == "__main__":
    unittest.main()
