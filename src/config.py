"""
Configuration management for AI Adoption Navigator
Handles mode, LLM provider and model selection.
API keys live only in environment variables - never written to disk.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import os

from src.db import data_dir
from src.llm_client import API_KEY_ENV_VARS, DEFAULT_MODELS, DEFAULT_OLLAMA_URL


LLM_PROVIDERS = {
    "claude": "Anthropic Claude",
    "openai": "OpenAI",
    "gemini": "Google Gemini",
    "groq": "Groq",
    "ollama": "Ollama (local, no API key)",
}

SUGGESTED_MODELS: Dict[str, List[str]] = {
    "claude": ["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5"],
    "openai": ["gpt-4o-mini", "gpt-4o"],
    "gemini": ["gemini-2.5-flash", "gemini-2.5-pro"],
    "groq": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
    "ollama": ["llama3.1", "qwen2.5", "mistral"],
}


class Config:
    """Application configuration manager"""

    def __init__(self, config_file: Optional[Path] = None):
        self.config_file = config_file or data_dir() / "config.json"
        self.config = self._load_config()

    def _default_config(self) -> Dict[str, Any]:
        return {
            "mode": "template",  # "template" or "llm"
            "llm_provider": "claude",
            "llm_model": DEFAULT_MODELS["claude"],
            "ollama_url": DEFAULT_OLLAMA_URL,
        }

    def _load_config(self) -> Dict[str, Any]:
        config = self._default_config()
        if self.config_file.exists():
            try:
                config.update(json.loads(self.config_file.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                pass
        return config

    def save_config(self):
        try:
            self.config_file.write_text(json.dumps(self.config, indent=2), encoding="utf-8")
        except OSError as e:
            print(f"Error saving config: {e}")

    def get(self, key: str) -> Any:
        return self.config.get(key)

    def update(self, **values: Any):
        self.config.update(values)
        self.save_config()

    def get_api_key(self, provider: Optional[str] = None) -> Optional[str]:
        env_var = API_KEY_ENV_VARS.get(provider or self.config["llm_provider"])
        return os.environ.get(env_var) if env_var else None

    def set_api_key(self, api_key: str, provider: Optional[str] = None):
        """Store the key in this process's environment only (not persisted)"""
        env_var = API_KEY_ENV_VARS.get(provider or self.config["llm_provider"])
        if env_var:
            os.environ[env_var] = api_key

    def is_llm_ready(self) -> bool:
        provider = self.config["llm_provider"]
        return provider == "ollama" or bool(self.get_api_key(provider))
