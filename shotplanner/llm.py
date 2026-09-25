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


class ProviderError(Exception):
    """Setup problem (missing package or key): reported as one line, no traceback."""


class GeminiProvider:
    # Set GEMINI_TEXT_MODEL to override. The default is the current stable Flash
    # model as listed in the Gemini API model docs (2026-09); check it there if a call fails.
    def __init__(self, model=None):
        self.model = model or os.environ.get("GEMINI_TEXT_MODEL", "gemini-3.8-flash")
        self.label = f"gemini:{self.model}"

    def generate_json(self, system, prompt):
        try:
            from google import genai
        except ImportError:
            raise ProviderError("the Gemini provider needs google-genai: "
                                "python3 -m pip install google-genai python-dotenv")
        try:
            from dotenv import load_dotenv
            load_dotenv(os.path.join(HERE, ".env"))
        except ImportError:
            pass  # .env support is optional; a key already in the environment still works
        if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
            raise ProviderError("GEMINI_API_KEY is not set (put it in .env; see .env.example)")
        try:
            client = genai.Client()
            resp = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config={"system_instruction": system, "response_mime_type": "application/json",
                        "temperature": 0.4,
                        # no tools are passed; turning this off also silences the SDK's AFC warning
                        "automatic_function_calling": {"disable": True}},
            )
        except Exception as e:  # network, quota, auth, unknown model id
            msg = str(e).splitlines()[0]
            msg = msg[:240] + ("..." if len(msg) > 240 else "")
            raise ProviderError(f"Gemini call failed with model {self.model!r}: {msg} "
                                "If the model id is the problem, set GEMINI_TEXT_MODEL (or pass --model).")
        if not resp.text:
            raise ProviderError(f"Gemini returned no text (model {self.model!r}); the response may have been blocked")
        return resp.text


PROVIDERS = {"gemini": GeminiProvider}


def get(name, model=None):
    if name not in PROVIDERS:
        raise SystemExit(f"unknown LLM provider {name!r}; have {sorted(PROVIDERS)}")
    return PROVIDERS[name](model)
