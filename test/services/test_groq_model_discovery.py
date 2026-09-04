import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def _response(payload, raise_for_status=None):
    return SimpleNamespace(
        json=lambda: payload,
        raise_for_status=raise_for_status or (lambda: None),
    )


class TestGetGroqModelIds(unittest.TestCase):
    """Populates the Groq model dropdown from the live API.

    It runs during Streamlit page render, so it must never raise and never
    block: a failure has to degrade to an empty list, letting the user type a
    model name manually instead of breaking the page.
    """

    @classmethod
    def setUpClass(cls):
        import webui.Main as webui_main

        # st.cache_data memoises across calls; use the undecorated function so
        # each test sees its own patched response.
        cls.fetch = staticmethod(webui_main.get_groq_model_ids.__wrapped__)
        cls.module = webui_main

    def _fetch(self, payload, api_key="gsk_test", base_url=""):
        with patch.object(
            self.module.requests, "get", return_value=_response(payload)
        ) as get:
            return self.fetch(api_key, base_url), get

    def test_no_api_key_short_circuits_without_a_request(self):
        with patch.object(self.module.requests, "get") as get:
            self.assertEqual(self.fetch("", ""), [])
        get.assert_not_called()

    def test_model_ids_are_extracted_sorted_and_deduplicated(self):
        payload = {
            "data": [
                {"id": "llama-3.3-70b"},
                {"id": "gemma2-9b"},
                {"id": "llama-3.3-70b"},
            ]
        }

        models, _ = self._fetch(payload)

        self.assertEqual(models, ["gemma2-9b", "llama-3.3-70b"])

    def test_malformed_entries_are_skipped_not_fatal(self):
        payload = {
            "data": [
                {"id": "good-model"},
                {"no_id": True},
                {"id": ""},
                {"id": "   "},
                {"id": 123},
                "not-a-dict",
                None,
            ]
        }

        models, _ = self._fetch(payload)

        self.assertEqual(models, ["good-model"])

    def test_ids_are_stripped(self):
        models, _ = self._fetch({"data": [{"id": "  spaced-model  "}]})

        self.assertEqual(models, ["spaced-model"])

    def test_missing_data_key_yields_an_empty_list(self):
        models, _ = self._fetch({})

        self.assertEqual(models, [])

    def test_network_failure_degrades_to_an_empty_list(self):
        with patch.object(
            self.module.requests, "get", side_effect=OSError("connection refused")
        ):
            self.assertEqual(self.fetch("gsk_test", ""), [])

    def test_http_error_degrades_to_an_empty_list(self):
        def boom():
            raise RuntimeError("401 Unauthorized")

        with patch.object(
            self.module.requests,
            "get",
            return_value=_response({}, raise_for_status=boom),
        ):
            self.assertEqual(self.fetch("gsk_test", ""), [])

    def test_request_carries_the_api_key_and_a_timeout(self):
        # No timeout would hang the Streamlit render thread.
        _, get = self._fetch({"data": []})

        kwargs = get.call_args.kwargs
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer gsk_test")
        self.assertTrue(kwargs["timeout"])

    def test_default_base_url_is_used_when_unset(self):
        _, get = self._fetch({"data": []}, base_url="")

        self.assertEqual(
            get.call_args.args[0], "https://api.groq.com/openai/v1/models"
        )

    def test_custom_base_url_is_normalised(self):
        for base_url in (
            "https://proxy.example/v1",
            "https://proxy.example/v1/",
            "  https://proxy.example/v1/  ",
        ):
            with self.subTest(base_url=base_url):
                _, get = self._fetch({"data": []}, base_url=base_url)
                self.assertEqual(
                    get.call_args.args[0], "https://proxy.example/v1/models"
                )


if __name__ == "__main__":
    unittest.main()
