import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models import const
from app.models.schema import VideoParams
from app.services import material
from app.services import task as tm

ERROR_STRING = "Error: [openai] api_key is not set"


class TestGenerateTermsRejectsErrorStrings(unittest.TestCase):
    """`llm.generate_terms()` returns an "Error: ..." string instead of a list
    when the LLM call fails. A string is iterable, so an unguarded value flows
    downstream one character at a time."""

    def setUp(self):
        self.params = VideoParams(video_subject="coffee")

    def _generate(self, llm_return):
        with patch.object(tm.llm, "generate_terms", return_value=llm_return), patch.object(
            tm.sm.state, "update_task"
        ) as update_task:
            return tm.generate_terms("task-1", self.params, "a script"), update_task

    def test_error_string_is_rejected(self):
        terms, update_task = self._generate(ERROR_STRING)

        self.assertIsNone(terms)
        update_task.assert_called_once()
        self.assertEqual(
            update_task.call_args.kwargs["state"], const.TASK_STATE_FAILED
        )

    def test_any_non_list_return_is_rejected(self):
        for value in ("", "plain text", {"terms": ["a"]}, 42, None):
            with self.subTest(value=value):
                terms, _ = self._generate(value)
                self.assertIsNone(terms)

    def test_valid_list_is_passed_through(self):
        self.params.match_materials_to_script = True  # skip the rerank branch
        terms, update_task = self._generate(["coffee shop", "latte art"])

        self.assertEqual(terms, ["coffee shop", "latte art"])
        update_task.assert_not_called()

    def test_explicit_user_terms_are_still_accepted(self):
        self.params.video_terms = "coffee, latte"
        self.params.match_materials_to_script = True

        with patch.object(tm.sm.state, "update_task"):
            terms = tm.generate_terms("task-1", self.params, "a script")

        self.assertEqual(terms, ["coffee", "latte"])


class TestErrorStringNeverReachesTheMaterialSearch(unittest.TestCase):
    def test_download_videos_would_search_per_character(self):
        """Shows why the guard matters, using the real download_videos()."""
        issued = []

        def fake_search(search_term, minimum_duration, video_aspect):
            issued.append(search_term)
            return []

        with patch.object(material, "search_videos_pexels", side_effect=fake_search):
            material.download_videos(
                task_id="t", search_terms=ERROR_STRING, audio_duration=5
            )

        # One API call per character of the error message.
        self.assertEqual(len(issued), len(ERROR_STRING))
        self.assertEqual(issued[:5], ["E", "r", "r", "o", "r"])

    def test_guarded_value_issues_no_searches(self):
        issued = []

        def fake_search(search_term, minimum_duration, video_aspect):
            issued.append(search_term)
            return []

        params = VideoParams(video_subject="coffee")
        with patch.object(tm.llm, "generate_terms", return_value=ERROR_STRING), patch.object(
            tm.sm.state, "update_task"
        ):
            terms = tm.generate_terms("task-1", params, "a script")

        with patch.object(material, "search_videos_pexels", side_effect=fake_search):
            material.download_videos(
                task_id="t", search_terms=terms or [], audio_duration=5
            )

        self.assertEqual(issued, [])


if __name__ == "__main__":
    unittest.main()
