import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services import llm


class TestStripCodeFence(unittest.TestCase):
    """Models routinely wrap JSON in a markdown fence despite being told not
    to. Without stripping it, json.loads fails and the whole retry budget is
    spent on a response that was actually correct."""

    def test_bare_json_is_untouched(self):
        self.assertEqual(llm._strip_code_fence('["a"]'), '["a"]')

    def test_language_tagged_fence_is_removed(self):
        self.assertEqual(llm._strip_code_fence('```json\n["a"]\n```'), '["a"]')

    def test_plain_fence_is_removed(self):
        self.assertEqual(llm._strip_code_fence('```\n["a"]\n```'), '["a"]')

    def test_surrounding_whitespace_is_trimmed(self):
        self.assertEqual(llm._strip_code_fence('  ["a"]  '), '["a"]')

    def test_result_is_parseable_json(self):
        import json

        for raw in ('["a","b"]', '```json\n["a","b"]\n```', '```\n["a","b"]\n```'):
            with self.subTest(raw=raw):
                self.assertEqual(json.loads(llm._strip_code_fence(raw)), ["a", "b"])


class TestGetResponseField(unittest.TestCase):
    """Reads a field from either a dict or an SDK response object, because
    provider SDKs differ on which they return."""

    def test_reads_from_a_dict(self):
        self.assertEqual(llm._get_response_field({"output": 1}, "output"), 1)

    def test_reads_from_an_object_attribute(self):
        self.assertEqual(
            llm._get_response_field(types.SimpleNamespace(output=2), "output"), 2
        )

    def test_missing_key_returns_none(self):
        self.assertIsNone(llm._get_response_field({"a": 1}, "missing"))

    def test_missing_attribute_returns_none(self):
        self.assertIsNone(
            llm._get_response_field(types.SimpleNamespace(a=1), "missing")
        )

    def test_none_and_scalars_do_not_raise(self):
        for value in (None, 5, "text", []):
            with self.subTest(value=value):
                self.assertIsNone(llm._get_response_field(value, "output"))


class TestExtractChatCompletionText(unittest.TestCase):
    """OpenAI-compatible gateways return HTTP 200 with an empty payload when a
    request is content-filtered. Each hole must produce a diagnosable error
    rather than an AttributeError from deep inside the SDK object."""

    def _response(self, choices):
        return types.SimpleNamespace(choices=choices)

    def test_extracts_the_message_content(self):
        response = self._response(
            [types.SimpleNamespace(message=types.SimpleNamespace(content="hello"))]
        )

        self.assertEqual(llm._extract_chat_completion_text(response, "openai"), "hello")

    def test_missing_choices_raises_a_named_error(self):
        for response in (self._response([]), self._response(None), types.SimpleNamespace()):
            with self.subTest(response=response):
                with self.assertRaises(ValueError) as ctx:
                    llm._extract_chat_completion_text(response, "openai")
                self.assertIn("[openai] returned empty choices", str(ctx.exception))

    def test_missing_message_raises_a_named_error(self):
        response = self._response([types.SimpleNamespace(message=None)])

        with self.assertRaises(ValueError) as ctx:
            llm._extract_chat_completion_text(response, "openai")

        self.assertIn("[openai] returned empty message", str(ctx.exception))

    def test_missing_content_raises_a_named_error(self):
        response = self._response(
            [types.SimpleNamespace(message=types.SimpleNamespace(content=None))]
        )

        with self.assertRaises(ValueError) as ctx:
            llm._extract_chat_completion_text(response, "openai")

        self.assertIn("[openai]", str(ctx.exception))

    def test_the_provider_name_is_always_in_the_error(self):
        # The message goes back to the user, so it has to say which provider.
        with self.assertRaises(ValueError) as ctx:
            llm._extract_chat_completion_text(self._response([]), "moonshot")

        self.assertIn("moonshot", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
