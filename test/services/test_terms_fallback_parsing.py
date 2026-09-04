import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services import llm


class TestTermsFallbackParsing(unittest.TestCase):
    """When the model wraps its JSON array in prose, generate_terms() falls back
    to a regex extraction. That fallback must apply the same list-of-strings
    validation as the primary parse, or non-string terms reach the material
    search."""

    def _generate(self, response):
        with patch.object(llm, "_generate_response", return_value=response):
            return llm.generate_terms("coffee", "a script", amount=3)

    def test_prose_wrapped_string_array_is_extracted(self):
        result = self._generate('Sure! Here you go: ["coffee shop", "latte art"]')

        self.assertEqual(result, ["coffee shop", "latte art"])

    def test_clean_json_array_still_parses(self):
        result = self._generate('["coffee shop", "latte art"]')

        self.assertEqual(result, ["coffee shop", "latte art"])

    def test_prose_wrapped_non_string_elements_are_rejected(self):
        for response in (
            "Here you go: [1, 2, 3]",
            'Sure: [{"term": "coffee"}]',
            "Result: [null, null]",
            'Mixed: ["coffee", 7]',
        ):
            with self.subTest(response=response):
                result = self._generate(response)

                # Rejected rather than passed through as non-strings.
                self.assertTrue(
                    result == [] or all(isinstance(t, str) for t in result),
                    f"non-string terms leaked: {result!r}",
                )

    def test_every_returned_term_is_a_string(self):
        # The property that actually matters downstream.
        result = self._generate("Here you go: [1, 2, 3]")

        self.assertTrue(all(isinstance(term, str) for term in result))


if __name__ == "__main__":
    unittest.main()
