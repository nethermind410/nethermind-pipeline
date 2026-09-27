"""Vendor-neutral HTTP adapters.

Adapters are intentionally thin: transport only. Brain policy, routing, budgets,
and evidence selection stay in the Harness/AdaptiveBrain.
"""
import json
import time
import urllib.error
import urllib.request
from .providers import BrainProvider, ProviderResult

class ProviderUnavailable(RuntimeError): pass
class ProviderTimeout(RuntimeError): pass
class ProviderProtocolError(RuntimeError): pass

def _extract_json(text):
    text=text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start=text.find("{"); end=text.rfind("}")
        if start >= 0 and end > start:
            try: return json.loads(text[start:end+1])
            except json.JSONDecodeError: pass
    raise ProviderProtocolError("provider did not return valid JSON")

def _result(data, model):
    required=("decision","confidence","reason","evidence","scores")
    if not all(k in data for k in required):
        raise ProviderProtocolError("provider response missing required fields")
    return ProviderResult(
        data["decision"], float(data["confidence"]), str(data["reason"]),
        list(data["evidence"]), dict(data["scores"]), model,
        float(data.get("estimated_cost",0)), float(data.get("actual_cost",0)),
    )

class OpenAICompatibleProvider(BrainProvider):
    modality="multimodal"
    def __init__(self, config, *, capability="brain.reasoning"):
        self.config=config; self.name=config.name; self.capability=capability
    def analyse(self, packet):
        if not self.config.configured:
            raise ProviderUnavailable(f"{self.name} is not configured")
        body={
            "model":self.config.model,
            "messages":[
                {"role":"system","content":"Return ONLY JSON matching ProviderResult. Judge only supplied evidence; do not invent context."},
                {"role":"user","content":json.dumps(packet.to_dict(),ensure_ascii=False,sort_keys=True)},
            ],
            "temperature":0,
            "response_format":{"type":"json_object"},
        }
        headers={"Content-Type":"application/json"}
        if self.config.api_key: headers["Authorization"]="Bearer "+self.config.api_key
        return _request_with_retry(self.config, "/chat/completions", body, headers, self.name)

class OllamaProvider(BrainProvider):
    name="ollama-local"; modality="multimodal"
    def __init__(self, config):
        self.config=config
    def analyse(self, packet):
        if not self.config.configured or not self.config.model:
            raise ProviderUnavailable("ollama-local is not configured with a model")
        body={
            "model":self.config.model,
            "stream":False,
            "format":"json",
            "prompt":"Return ONLY JSON matching ProviderResult. Judge only supplied evidence.\n"+json.dumps(packet.to_dict(),ensure_ascii=False,sort_keys=True),
        }
        return _request_with_retry(self.config, "/api/generate", body, {"Content-Type":"application/json"}, self.name, ollama=True)

def _request_with_retry(config, path, body, headers, model, ollama=False):
    url=config.base_url.rstrip("/") + path
    last=None
    for attempt in range(config.max_retries+1):
        try:
            req=urllib.request.Request(url,json.dumps(body).encode(),headers=headers,method="POST")
            with urllib.request.urlopen(req,timeout=config.timeout_seconds) as response:
                payload=json.loads(response.read().decode())
            raw=payload.get("response","") if ollama else payload["choices"][0]["message"]["content"]
            return _result(_extract_json(raw),model)
        except TimeoutError as exc:
            last=exc
            if attempt < config.max_retries: time.sleep(min(2**attempt,4))
        except urllib.error.HTTPError as exc:
            last=exc
            if exc.code in (408,429,500,502,503,504) and attempt < config.max_retries:
                time.sleep(min(2**attempt,4)); continue
            raise ProviderUnavailable(f"{model} HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise ProviderUnavailable(f"{model} unavailable") from exc
        except (KeyError, json.JSONDecodeError, ProviderProtocolError) as exc:
            raise ProviderProtocolError(f"{model} invalid response") from exc
    raise ProviderTimeout(f"{model} timed out after {config.max_retries+1} attempts") from last
