import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config import config
from app.services import material
from app.models.schema import VideoAspect

# portrait resolution used by the default aspect
WIDTH, HEIGHT = VideoAspect.portrait.to_resolution()


def _response(payload):
    return SimpleNamespace(json=lambda: payload)


class _SearchResilienceTestCase(unittest.TestCase):
    def setUp(self):
        self.original_app = dict(config.app)
        self.original_proxy = dict(config.proxy)
        config.proxy.clear()

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app)
        config.proxy.clear()
        config.proxy.update(self.original_proxy)

    def _search(self, search_fn, payload):
        with patch.object(material.requests, "get", return_value=_response(payload)):
            return search_fn(
                search_term="cat",
                minimum_duration=3,
                video_aspect=VideoAspect.portrait,
            )


class TestPexelsSearchResilience(_SearchResilienceTestCase):
    """One malformed entry must not discard the whole batch.

    Every field used to be read with [], so a single result missing a key
    raised out to the function-level `except` and returned [].
    """

    def setUp(self):
        super().setUp()
        config.app["pexels_api_keys"] = ["pexels-key"]

    def _good(self, link):
        return {
            "duration": 10,
            "video_files": [{"width": WIDTH, "height": HEIGHT, "link": link}],
        }

    def test_valid_results_survive_a_malformed_neighbour(self):
        payload = {
            "videos": [
                self._good("https://v.example/first.mp4"),
                {"video_files": []},                      # no duration
                {"duration": 10},                         # no video_files
                {"duration": 10, "video_files": [{}]},    # file without w/h/link
                {"duration": "not-a-number", "video_files": []},
                self._good("https://v.example/second.mp4"),
            ]
        }

        items = self._search(material.search_videos_pexels, payload)

        self.assertEqual(
            [i.url for i in items],
            ["https://v.example/first.mp4", "https://v.example/second.mp4"],
        )

    def test_entry_without_a_link_is_skipped(self):
        payload = {
            "videos": [{"duration": 10, "video_files": [{"width": WIDTH, "height": HEIGHT}]}]
        }

        self.assertEqual(self._search(material.search_videos_pexels, payload), [])

    def test_short_videos_are_still_filtered_out(self):
        payload = {"videos": [dict(self._good("https://v.example/x.mp4"), duration=1)]}

        self.assertEqual(self._search(material.search_videos_pexels, payload), [])

    def test_normal_payload_still_parses(self):
        payload = {"videos": [self._good("https://v.example/ok.mp4")]}

        items = self._search(material.search_videos_pexels, payload)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].provider, "pexels")
        self.assertEqual(items[0].duration, 10)


class TestPixabaySearchResilience(_SearchResilienceTestCase):
    def setUp(self):
        super().setUp()
        config.app["pixabay_api_keys"] = ["pixabay-key"]

    def _good(self, url):
        return {"duration": 10, "videos": {"large": {"width": WIDTH, "url": url}}}

    def test_valid_results_survive_a_malformed_neighbour(self):
        payload = {
            "hits": [
                self._good("https://v.example/first.mp4"),
                {"videos": {}},                                  # no duration
                {"duration": 10},                                # no videos
                {"duration": 10, "videos": {"large": {}}},       # no width/url
                self._good("https://v.example/second.mp4"),
            ]
        }

        items = self._search(material.search_videos_pixabay, payload)

        self.assertEqual(
            [i.url for i in items],
            ["https://v.example/first.mp4", "https://v.example/second.mp4"],
        )

    def test_narrow_videos_are_skipped(self):
        payload = {"hits": [{"duration": 10, "videos": {"tiny": {"width": 1, "url": "u"}}}]}

        self.assertEqual(self._search(material.search_videos_pixabay, payload), [])

    def test_normal_payload_still_parses(self):
        payload = {"hits": [self._good("https://v.example/ok.mp4")]}

        items = self._search(material.search_videos_pixabay, payload)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].provider, "pixabay")


if __name__ == "__main__":
    unittest.main()
