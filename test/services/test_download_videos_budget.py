import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config import config
from app.models.schema import MaterialInfo, VideoConcatMode
from app.services import material


class TestDownloadVideosBudget(unittest.TestCase):
    """`download_videos` decides how much stock footage to fetch.

    Every download is a third-party API call plus disk. Fetching too few leaves
    the timeline short of the narration; fetching too many burns quota and time
    on clips that never make the cut.
    """

    def setUp(self):
        self.original_app = dict(config.app)
        self.original_proxy = dict(config.proxy)
        config.proxy.clear()
        config.app["pexels_api_keys"] = ["k"]
        self.downloaded = []

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app)
        config.proxy.clear()
        config.proxy.update(self.original_proxy)

    def _run(self, results, audio_duration, **kwargs):
        def fake_search(search_term, minimum_duration, video_aspect):
            return results.get(search_term, [])

        def fake_save(video_url, save_dir=""):
            self.downloaded.append(video_url)
            return f"/saved/{len(self.downloaded)}.mp4"

        with patch.object(material, "search_videos_pexels", side_effect=fake_search), \
             patch.object(material, "save_video", side_effect=fake_save):
            return material.download_videos(
                task_id="budget",
                search_terms=list(results),
                audio_duration=audio_duration,
                **kwargs,
            )

    def _items(self, urls, duration=5):
        return [MaterialInfo(provider="pexels", url=u, duration=duration) for u in urls]

    def test_stops_once_the_audio_duration_is_covered(self):
        results = {"a": self._items([f"https://v/{i}.mp4" for i in range(10)])}

        paths = self._run(results, audio_duration=10, max_clip_duration=5,
                          video_concat_mode=VideoConcatMode.sequential)

        # 5s clips covering 10s of audio: stops just after passing the budget.
        self.assertLessEqual(len(paths), 3)
        self.assertGreaterEqual(len(paths), 2)

    def test_downloads_nothing_when_no_results_are_found(self):
        paths = self._run({"a": []}, audio_duration=10)

        self.assertEqual(paths, [])
        self.assertEqual(self.downloaded, [])

    def test_duplicate_urls_across_terms_are_downloaded_once(self):
        shared = "https://v/shared.mp4"
        results = {
            "a": self._items([shared, "https://v/a1.mp4"]),
            "b": self._items([shared, "https://v/b1.mp4"]),
        }

        self._run(results, audio_duration=100,
                  video_concat_mode=VideoConcatMode.sequential)

        self.assertEqual(self.downloaded.count(shared), 1)

    def test_a_failed_save_does_not_abort_the_batch(self):
        results = {"a": self._items([f"https://v/{i}.mp4" for i in range(3)])}
        calls = {"n": 0}

        def flaky_save(video_url, save_dir=""):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("network blip")
            return f"/saved/{calls['n']}.mp4"

        def fake_search(search_term, minimum_duration, video_aspect):
            return results.get(search_term, [])

        with patch.object(material, "search_videos_pexels", side_effect=fake_search), \
             patch.object(material, "save_video", side_effect=flaky_save):
            paths = material.download_videos(
                task_id="budget", search_terms=["a"], audio_duration=100,
                video_concat_mode=VideoConcatMode.sequential,
            )

        self.assertTrue(paths, "one bad download aborted the whole batch")

    def test_an_empty_save_result_is_not_added_to_the_timeline(self):
        results = {"a": self._items(["https://v/1.mp4"])}

        def empty_save(video_url, save_dir=""):
            return ""  # save_video returns "" when the file fails validation

        def fake_search(search_term, minimum_duration, video_aspect):
            return results.get(search_term, [])

        with patch.object(material, "search_videos_pexels", side_effect=fake_search), \
             patch.object(material, "save_video", side_effect=empty_save):
            paths = material.download_videos(
                task_id="budget", search_terms=["a"], audio_duration=10,
                video_concat_mode=VideoConcatMode.sequential,
            )

        self.assertEqual(paths, [])

    def test_returned_paths_are_the_saved_files(self):
        results = {"a": self._items(["https://v/1.mp4"])}

        paths = self._run(results, audio_duration=1,
                          video_concat_mode=VideoConcatMode.sequential)

        self.assertTrue(all(p.startswith("/saved/") for p in paths))

    def test_unknown_source_falls_back_to_pexels(self):
        results = {"a": self._items(["https://v/1.mp4"])}

        paths = self._run(results, audio_duration=1, source="not-a-provider",
                          video_concat_mode=VideoConcatMode.sequential)

        self.assertTrue(paths)


if __name__ == "__main__":
    unittest.main()
