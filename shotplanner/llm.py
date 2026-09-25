"""
LLM providers for beat planning, kept behind one small interface so the
planner doesn't depend on any one vendor.

    provider.generate_json(system, prompt) -> str   (a JSON document)

To add a provider, write a class with that method and register it in
PROVIDERS. Gemini is the only one wired in so far, because the repo
already uses google-genai and GEMINI_API_KEY (see gen_visuals.py).
"""
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class GeminiProvider:
    # Set GEMINI_TEXT_MODEL to override. The default is the current stable Flash
    # model as listed in the Gemini API model docs (2026-09); check it there if a call fails.
    def __init__(self, model=None):
        self.model = model or os.environ.get("GEMINI_TEXT_MODEL", "gemini-3.8-flash")
        self.label = f"gemini:{self.model}"

    def generate_json(self, system, prompt):
        from dotenv import load_dotenv
        from google import genai
        load_dotenv(os.path.join(HERE, ".env"))
        client = genai.Client()
        resp = client.models.generate_content(
            model=self.model,
            contents=prompt,
            config={"system_instruction": system, "response_mime_type": "application/json",
                    "temperature": 0.4},
        )
        return resp.text


PROVIDERS = {"gemini": GeminiProvider}


def get(name, model=None):
    if name not in PROVIDERS:
        raise SystemExit(f"unknown LLM provider {name!r}; have {sorted(PROVIDERS)}")
    return PROVIDERS[name](model)
