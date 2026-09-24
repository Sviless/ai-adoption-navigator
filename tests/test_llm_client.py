"""Gemini REST call with a mocked HTTP response - no network or real key needed"""

import unittest
from unittest import mock

from src.llm_client import UniversalLLMClient, list_models


def fake_response(status, body):
    response = mock.Mock(status_code=status, text=str(body))
    response.json.return_value = body
    return response


class TestGeminiClient(unittest.TestCase):
    def setUp(self):
        self.client = UniversalLLMClient(provider="gemini", model="gemini-2.5-flash", api_key="test-key")

    @mock.patch("requests.post")
    def test_success_returns_text_and_sends_key_in_header(self, post):
        post.return_value = fake_response(200, {"candidates": [{"content": {"parts": [
            {"text": "thinking...", "thought": True}, {"text": '{"ok": true}'}]}}]})
        self.assertEqual(self.client.generate_json("hi"), {"ok": True})
        url = post.call_args.args[0]
        kwargs = post.call_args.kwargs
        self.assertTrue(url.endswith("/gemini-2.5-flash:generateContent"))
        self.assertNotIn("test-key", url)  # key goes in the header, never the URL
        self.assertEqual(kwargs["headers"]["x-goog-api-key"], "test-key")
        self.assertEqual(kwargs["json"]["generationConfig"]["responseMimeType"], "application/json")

    @mock.patch("requests.post")
    def test_api_error_message_is_surfaced(self, post):
        post.return_value = fake_response(400, {"error": {"message": "API key not valid."}})
        with self.assertRaisesRegex(Exception, "API key not valid"):
            self.client.generate("hi")

    @mock.patch("requests.post")
    def test_blocked_prompt(self, post):
        post.return_value = fake_response(200, {"promptFeedback": {"blockReason": "SAFETY"}})
        with self.assertRaisesRegex(Exception, "SAFETY"):
            self.client.generate("hi")


class TestListModels(unittest.TestCase):
    @mock.patch("requests.get")
    def test_gemini_lists_text_models_newest_first(self, get):
        def model(name, methods=("generateContent",)):
            return {"name": f"models/{name}", "supportedGenerationMethods": list(methods)}
        get.return_value = fake_response(200, {"models": [
            model("gemini-2.5-pro"), model("gemini-3.8-flash"), model("gemini-2.5-flash"),
            model("gemini-3.8-flash-preview-tts"), model("gemini-embedding-001", ["embedContent"]),
            model("gemini-3.8-flash-image"),
        ]})
        names = list_models("gemini", api_key="test-key")
        self.assertEqual(names[0], "gemini-3.8-flash")
        self.assertIn("gemini-2.5-pro", names)
        self.assertFalse(any(x in n for n in names for x in ("tts", "embedding", "image")))
        self.assertEqual(get.call_args.kwargs["headers"]["x-goog-api-key"], "test-key")

    def test_gemini_needs_key(self):
        with self.assertRaisesRegex(ValueError, "API key"):
            list_models("gemini", api_key=None)

    @mock.patch("requests.get")
    def test_gemini_error_is_surfaced(self, get):
        get.return_value = fake_response(400, {"error": {"message": "API key not valid."}})
        with self.assertRaisesRegex(Exception, "API key not valid"):
            list_models("gemini", api_key="bad")

    @mock.patch("requests.get")
    def test_ollama_lists_installed_models(self, get):
        get.return_value = fake_response(200, {"models": [{"name": "qwen2.5:latest"}, {"name": "llama3.1:8b"}]})
        get.return_value.raise_for_status = mock.Mock()
        self.assertEqual(list_models("ollama"), ["llama3.1:8b", "qwen2.5:latest"])


if __name__ == "__main__":
    unittest.main()
