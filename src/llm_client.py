"""
Universal LLM Client - Supports cloud providers (OpenAI, Gemini, Claude, Groq)
and a fully local option (Ollama). Adapted from the AI Resource Capacity Planner.
"""

from typing import Any, Dict, Optional
import json
import os


API_KEY_ENV_VARS = {
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
    "groq": "GROQ_API_KEY",
}

DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.5-flash",
    "claude": "claude-opus-5",
    "groq": "llama-3.3-70b-versatile",
    "ollama": "llama3.1",
}

DEFAULT_OLLAMA_URL = "http://localhost:11434"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"

DEFAULT_SYSTEM_PROMPT = (
    "You are a senior AI transformation advisor with expertise in operational excellence, "
    "Lean, project management, AI governance (EU AI Act, NIST AI RMF), change management "
    "and workforce planning. You are pragmatic, evidence-based and people-centered. "
    "Never invent numbers: use only the figures you are given."
)


class UniversalLLMClient:
    """Universal client for multiple LLM providers"""

    def __init__(
        self,
        provider: str = "openai",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        base_url: Optional[str] = None,
    ):
        self.provider = provider.lower()
        self.api_key = api_key or os.environ.get(API_KEY_ENV_VARS.get(self.provider, ""), None)
        self.model = model or DEFAULT_MODELS.get(self.provider, "")
        self.system_prompt = system_prompt
        self.base_url = (base_url or DEFAULT_OLLAMA_URL).rstrip("/")

        if self.provider != "ollama" and not self.api_key:
            raise ValueError(f"No API key found for {self.provider}")

    def generate(self, prompt: str, max_tokens: int = 4000, json_mode: bool = False) -> str:
        """Generate text using the configured LLM provider"""
        callers = {
            "openai": self._call_openai,
            "gemini": self._call_gemini,
            "claude": self._call_claude,
            "groq": self._call_groq,
            "ollama": self._call_ollama,
        }
        if self.provider not in callers:
            raise ValueError(f"Unsupported provider: {self.provider}")
        try:
            return callers[self.provider](prompt, max_tokens, json_mode)
        except Exception as e:
            raise Exception(f"LLM API call failed ({self.provider}): {e}")

    def generate_json(self, prompt: str, max_tokens: int = 4000) -> Dict[str, Any]:
        """Generate and parse a JSON object response"""
        text = self.generate(
            prompt + "\n\nRespond with a single valid JSON object only, no markdown fences.",
            max_tokens=max_tokens,
            json_mode=True,
        )
        return parse_json_object(text)

    def _call_openai(self, prompt: str, max_tokens: int, json_mode: bool) -> str:
        try:
            import openai
        except ImportError:
            raise Exception("OpenAI library not installed. Install with: pip install openai")
        client = openai.OpenAI(api_key=self.api_key)
        kwargs: Dict[str, Any] = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.3,
            **kwargs,
        )
        return response.choices[0].message.content

    def _call_gemini(self, prompt: str, max_tokens: int, json_mode: bool) -> str:
        """Gemini REST API via requests - no SDK install needed (google-generativeai is deprecated)"""
        import requests

        config: Dict[str, Any] = {"temperature": 0.3, "maxOutputTokens": max_tokens}
        if json_mode:
            config["responseMimeType"] = "application/json"
        payload = {
            "systemInstruction": {"parts": [{"text": self.system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": config,
        }
        response = requests.post(
            f"{GEMINI_API_URL}/{self.model}:generateContent",
            headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
            json=payload, timeout=300,
        )
        data = response.json()
        if response.status_code != 200:
            message = data.get("error", {}).get("message", response.text[:300])
            raise Exception(f"Gemini API error {response.status_code}: {message}")

        candidates = data.get("candidates") or []
        if not candidates:
            reason = data.get("promptFeedback", {}).get("blockReason", "no candidates returned")
            raise Exception(f"Gemini returned no answer ({reason})")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        if not text:
            raise Exception(f"Gemini returned an empty answer (finish reason: {candidates[0].get('finishReason')})")
        return text

    def _call_claude(self, prompt: str, max_tokens: int, json_mode: bool) -> str:
        try:
            import anthropic
        except ImportError:
            raise Exception("Anthropic library not installed. Install with: pip install anthropic")
        client = anthropic.Anthropic(api_key=self.api_key)
        # Current Claude models do not accept temperature; JSON is requested in the prompt
        message = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=self.system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )
        if message.stop_reason == "refusal":
            raise Exception("Claude declined this request")
        return "".join(block.text for block in message.content if block.type == "text")

    def _call_groq(self, prompt: str, max_tokens: int, json_mode: bool) -> str:
        try:
            from groq import Groq
        except ImportError:
            raise Exception("Groq library not installed. Install with: pip install groq")
        client = Groq(api_key=self.api_key)
        kwargs: Dict[str, Any] = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.3,
            **kwargs,
        )
        return response.choices[0].message.content

    def _call_ollama(self, prompt: str, max_tokens: int, json_mode: bool) -> str:
        """Local LLM via Ollama - no API key, data never leaves the machine"""
        import requests

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": max_tokens},
        }
        if json_mode:
            payload["format"] = "json"
        try:
            response = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=300)
        except requests.ConnectionError:
            raise Exception(f"Cannot reach Ollama at {self.base_url}. Is it running? (ollama serve)")
        response.raise_for_status()
        return response.json()["message"]["content"]


MODEL_LISTING_PROVIDERS = ("gemini", "ollama")
# Gemini models that support generateContent but are not text/chat models
NON_TEXT_MODEL_HINTS = ("embedding", "tts", "image", "audio", "live", "aqa", "robotics")


def list_models(provider: str, api_key: Optional[str] = None, base_url: Optional[str] = None) -> list:
    """Models available to this account (Gemini) or installed locally (Ollama), newest-looking first"""
    import requests

    if provider == "gemini":
        if not api_key:
            raise ValueError("Paste your Gemini API key first")
        response = requests.get(GEMINI_API_URL, headers={"x-goog-api-key": api_key},
                                params={"pageSize": 1000}, timeout=30)
        data = response.json()
        if response.status_code != 200:
            raise Exception(data.get("error", {}).get("message", response.text[:300]))
        names = [
            m["name"].removeprefix("models/") for m in data.get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])
            and not any(hint in m["name"].lower() for hint in NON_TEXT_MODEL_HINTS)
        ]
        return sorted(set(names), key=_version_sort_key, reverse=True)

    if provider == "ollama":
        try:
            response = requests.get(f"{(base_url or DEFAULT_OLLAMA_URL).rstrip('/')}/api/tags", timeout=10)
        except requests.ConnectionError:
            raise Exception("Cannot reach Ollama. Is it running? (ollama serve)")
        response.raise_for_status()
        return sorted(m["name"] for m in response.json().get("models", []))

    raise ValueError(f"Model listing is not supported for {provider} - type the model name instead")


def _version_sort_key(name: str):
    """Sort 'gemini-3.8-flash' above 'gemini-2.5-pro': compare the version numbers found in the name"""
    import re
    numbers = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", name)]
    return (numbers, "preview" not in name and "exp" not in name, name)


def parse_json_object(text: str) -> Dict[str, Any]:
    """Extract the first JSON object from an LLM response"""
    start = text.find("{")
    end = text.rfind("}") + 1
    if start < 0 or end <= start:
        raise ValueError("No JSON object found in LLM response")
    return json.loads(text[start:end])
