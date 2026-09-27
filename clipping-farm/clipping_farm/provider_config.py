"""Environment-driven provider configuration. No credentials are stored in the repo."""
from dataclasses import dataclass
import os

@dataclass(frozen=True)
class ProviderConfig:
    name: str
    base_url: str
    api_key_env: str = ""
    model: str = ""
    timeout_seconds: float = 30.0
    max_retries: int = 2
    enabled: bool = True

    @property
    def api_key(self):
        return os.getenv(self.api_key_env, "") if self.api_key_env else ""

    @property
    def configured(self):
        return self.enabled and bool(self.base_url) and (not self.api_key_env or bool(self.api_key))

def load_provider_configs():
    return [
        ProviderConfig(
            "openai-compatible-cheap",
            os.getenv("CLIP_FARM_CHEAP_BASE_URL", ""),
            os.getenv("CLIP_FARM_CHEAP_API_KEY_ENV", ""),
            os.getenv("CLIP_FARM_CHEAP_MODEL", ""),
            float(os.getenv("CLIP_FARM_CHEAP_TIMEOUT", "30")),
            int(os.getenv("CLIP_FARM_CHEAP_RETRIES", "2")),
            os.getenv("CLIP_FARM_CHEAP_ENABLED", "1") != "0",
        ),
        ProviderConfig(
            "openai-compatible-premium",
            os.getenv("CLIP_FARM_PREMIUM_BASE_URL", ""),
            os.getenv("CLIP_FARM_PREMIUM_API_KEY_ENV", ""),
            os.getenv("CLIP_FARM_PREMIUM_MODEL", ""),
            float(os.getenv("CLIP_FARM_PREMIUM_TIMEOUT", "45")),
            int(os.getenv("CLIP_FARM_PREMIUM_RETRIES", "2")),
            os.getenv("CLIP_FARM_PREMIUM_ENABLED", "1") != "0",
        ),
        ProviderConfig(
            "ollama-local",
            os.getenv("CLIP_FARM_OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            "",
            os.getenv("CLIP_FARM_OLLAMA_MODEL", ""),
            float(os.getenv("CLIP_FARM_OLLAMA_TIMEOUT", "60")),
            int(os.getenv("CLIP_FARM_OLLAMA_RETRIES", "1")),
            os.getenv("CLIP_FARM_OLLAMA_ENABLED", "1") != "0",
        ),
    ]
