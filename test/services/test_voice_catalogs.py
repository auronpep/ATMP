import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config import config
from app.services import voice as vs


class TestProviderVoiceCatalogs(unittest.TestCase):
    """The dropdown strings these produce are re-parsed by `tts()` to pick a
    provider and pull the model/voice back out. Catalogue format and dispatch
    parsing are two halves of one contract — if the format drifts, dispatch
    silently sends the request somewhere else."""

    def test_siliconflow_entries_carry_provider_model_and_voice(self):
        for entry in vs.get_siliconflow_voices():
            with self.subTest(entry=entry):
                parts = entry.split(":")
                self.assertEqual(parts[0], "siliconflow")
                self.assertEqual(len(parts), 3, "tts() requires >= 3 segments")
                self.assertTrue(parts[1], "model segment must not be empty")
                self.assertTrue(entry.endswith(("-Male", "-Female")))

    def test_gemini_entries_are_prefixed_and_gendered(self):
        for entry in vs.get_gemini_voices():
            with self.subTest(entry=entry):
                self.assertTrue(entry.startswith("gemini:"))
                self.assertTrue(entry.endswith(("-Male", "-Female")))
                self.assertTrue(entry.split(":")[1])

    def test_mimo_entries_are_prefixed_and_gendered(self):
        for entry in vs.get_mimo_voices():
            with self.subTest(entry=entry):
                self.assertTrue(entry.startswith("mimo:"))
                self.assertTrue(entry.endswith(("-Male", "-Female")))
                self.assertTrue(entry.split(":")[1])

    def test_catalogs_are_non_empty_and_unique(self):
        for fn in (vs.get_siliconflow_voices, vs.get_gemini_voices, vs.get_mimo_voices):
            with self.subTest(catalog=fn.__name__):
                entries = fn()
                self.assertTrue(entries)
                self.assertEqual(len(entries), len(set(entries)))

    def test_every_catalog_entry_is_recognised_by_its_own_detector(self):
        # The detector each entry must match for tts() to route it correctly.
        for fn, detector in (
            (vs.get_siliconflow_voices, vs.is_siliconflow_voice),
            (vs.get_gemini_voices, vs.is_gemini_voice),
            (vs.get_mimo_voices, vs.is_mimo_voice),
        ):
            for entry in fn():
                with self.subTest(entry=entry):
                    self.assertTrue(detector(entry))

    def test_parse_voice_name_strips_the_gender_suffix_from_catalog_entries(self):
        for fn in (vs.get_siliconflow_voices, vs.get_gemini_voices, vs.get_mimo_voices):
            for entry in fn():
                with self.subTest(entry=entry):
                    parsed = vs.parse_voice_name(entry)
                    self.assertFalse(parsed.endswith(("-Male", "-Female")))


class TestChatterboxVoiceCatalog(unittest.TestCase):
    """Chatterbox is self-hosted, so its catalogue comes from user config."""

    def setUp(self):
        self.original = dict(config.chatterbox)

    def tearDown(self):
        config.chatterbox.clear()
        config.chatterbox.update(self.original)

    def test_unconfigured_still_yields_a_usable_default(self):
        config.chatterbox["voices"] = []

        self.assertEqual(vs.get_chatterbox_voices(), ["chatterbox:default-Female"])

    def test_list_entries_are_prefixed(self):
        config.chatterbox["voices"] = ["alpha", "beta"]

        self.assertEqual(
            vs.get_chatterbox_voices(), ["chatterbox:alpha", "chatterbox:beta"]
        )

    def test_comma_separated_string_is_accepted(self):
        config.chatterbox["voices"] = "alpha, beta"

        self.assertEqual(
            vs.get_chatterbox_voices(), ["chatterbox:alpha", "chatterbox:beta"]
        )

    def test_already_prefixed_entries_are_not_double_prefixed(self):
        config.chatterbox["voices"] = ["chatterbox:alpha"]

        self.assertEqual(vs.get_chatterbox_voices(), ["chatterbox:alpha"])

    def test_blank_entries_are_dropped(self):
        config.chatterbox["voices"] = ["alpha", "", "   "]

        self.assertEqual(vs.get_chatterbox_voices(), ["chatterbox:alpha"])


class TestAzureVoiceCatalog(unittest.TestCase):
    def test_catalog_is_large_and_sorted(self):
        voices = vs.get_all_azure_voices()

        self.assertGreater(len(voices), 100)
        self.assertEqual(voices, sorted(voices))

    def test_every_entry_carries_a_gender_suffix(self):
        for entry in vs.get_all_azure_voices()[:50]:
            with self.subTest(entry=entry):
                self.assertTrue(entry.endswith(("-Male", "-Female")))

    def test_locale_filter_narrows_the_catalog(self):
        filtered = vs.get_all_azure_voices(["zh-CN"])
        everything = vs.get_all_azure_voices()

        self.assertTrue(filtered)
        self.assertLess(len(filtered), len(everything))
        for entry in filtered:
            with self.subTest(entry=entry):
                self.assertTrue(entry.lower().startswith("zh-cn"))

    def test_v2_entries_are_detected_as_azure_v2(self):
        v2 = [v for v in vs.get_all_azure_voices() if "-V2-" in v]

        self.assertTrue(v2, "expected some V2 voices in the bundled catalog")
        for entry in v2[:10]:
            with self.subTest(entry=entry):
                self.assertTrue(vs.is_azure_v2_voice(entry))


if __name__ == "__main__":
    unittest.main()
