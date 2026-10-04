"""Provider-neutral image Vision contracts and adapters."""
from dataclasses import dataclass, asdict
import base64, hashlib, io, json, time, urllib.error, urllib.request
from pathlib import Path
from PIL import Image

MAX_FRAMES = 6
MAX_DIMENSION = 1280
MAX_PAYLOAD_BYTES = 4 * 1024 * 1024

class VisionProviderError(RuntimeError): pass
class VisionProviderUnavailable(VisionProviderError): pass
class VisionProviderTimeout(VisionProviderError): pass
class VisionProviderProtocolError(VisionProviderError): pass

@dataclass
class VisionRequest:
    job_id: str
    candidate_id: str
    task: str
    frames: list
    prompt_version: str = "vision-v1"
    quality_required: float = 0.78
    budget_remaining: float = 0.0

@dataclass
class VisionResult:
    composition: float
    action: float
    subject_visibility: float
    visual_novelty: float
    relevance: float
    continuity: float
    ocr_present: bool
    faces_present: bool
    objects: list
    visual_events: list
    evidence: list
    confidence: float
    model: str
    estimated_cost: float = 0.0
    actual_cost: float = 0.0

    def to_dict(self): return asdict(self)

def _bounded(v, name):
    try: v=float(v)
    except (TypeError, ValueError) as e: raise VisionProviderProtocolError(f"invalid {name}") from e
    if not 0.0 <= v <= 1.0: raise VisionProviderProtocolError(f"{name} outside 0..1")
    return v

def validate_vision_result(data):
    required=("composition","action","subject_visibility","visual_novelty","relevance",
              "continuity","ocr_present","faces_present","objects","visual_events",
              "evidence","confidence")
    missing=[k for k in required if k not in data]
    if missing: raise VisionProviderProtocolError("vision response missing: "+", ".join(missing))
    return VisionResult(
        composition=_bounded(data["composition"],"composition"),
        action=_bounded(data["action"],"action"),
        subject_visibility=_bounded(data["subject_visibility"],"subject_visibility"),
        visual_novelty=_bounded(data["visual_novelty"],"visual_novelty"),
        relevance=_bounded(data["relevance"],"relevance"),
        continuity=_bounded(data["continuity"],"continuity"),
        ocr_present=bool(data["ocr_present"]),
        faces_present=bool(data["faces_present"]),
        objects=list(data["objects"]),
        visual_events=list(data["visual_events"]),
        evidence=list(data["evidence"]),
        confidence=_bounded(data["confidence"],"confidence"),
        model=str(data.get("model","external-vision")),
        estimated_cost=float(data.get("estimated_cost",0.0)),
        actual_cost=float(data.get("actual_cost",0.0)),
    )

def _image_data_url(path):
    p=Path(path)
    if not p.exists() or not p.is_file(): raise VisionProviderProtocolError(f"frame missing: {p}")
    raw=p.read_bytes()
    if not raw: raise VisionProviderProtocolError(f"empty frame: {p}")
    try:
        with Image.open(io.BytesIO(raw)) as im:
            im.verify()
        with Image.open(io.BytesIO(raw)) as im:
            im=im.convert("RGB")
            im.thumbnail((MAX_DIMENSION,MAX_DIMENSION), Image.Resampling.LANCZOS)
            buf=io.BytesIO()
            im.save(buf,format="JPEG",quality=82,optimize=True)
            encoded=buf.getvalue()
    except Exception as e:
        raise VisionProviderProtocolError(f"invalid image frame: {p}") from e
    return "data:image/jpeg;base64,"+base64.b64encode(encoded).decode("ascii"), len(encoded)

def prepare_image_payload(frames):
    if len(frames)>MAX_FRAMES: frames=frames[:MAX_FRAMES]
    content=[]; total=0
    for f in frames:
        url,size=_image_data_url(f["path"])
        total += size
        if total > MAX_PAYLOAD_BYTES:
            raise VisionProviderProtocolError("vision image payload exceeds 4MB")
        content.append({"type":"image_url","image_url":{"url":url,"detail":"low"}})
    if not content: raise VisionProviderProtocolError("no usable frames")
    return content

def _extract_json(text):
    try: return json.loads(text.strip())
    except json.JSONDecodeError as e:
        raise VisionProviderProtocolError("vision provider returned invalid JSON") from e

class OpenAICompatibleVisionProvider:
    modality="image"
    def __init__(self, config):
        self.config=config; self.name=config.name
    def analyse_images(self, request):
        if not self.config.configured: raise VisionProviderUnavailable(f"{self.name} not configured")
        images=prepare_image_payload(request.frames)
        prompt=("Analyse these frames for the candidate. Return ONLY JSON with fields "
                "composition, action, subject_visibility, visual_novelty, relevance, continuity, "
                "ocr_present, faces_present, objects, visual_events, evidence, confidence, model. "
                "Use only visible evidence; do not infer facts not visible. All score/confidence fields 0..1. "
                f"Task: {request.task}. Prompt version: {request.prompt_version}.")
        body={"model":self.config.model,"messages":[
            {"role":"system","content":"You are a visual evidence extractor. Return strict JSON only."},
            {"role":"user","content":[{"type":"text","text":prompt}]+images}],
            "temperature":0,"response_format":{"type":"json_object"}}
        headers={"Content-Type":"application/json"}
        if self.config.api_key: headers["Authorization"]="Bearer "+self.config.api_key
        result=_request(self.config,"/chat/completions",body,headers,self.name)
        result.model=self.config.model or self.name
        return result

def _request(config,path,body,headers,name):
    last=None
    for attempt in range(config.max_retries+1):
        try:
            req=urllib.request.Request(config.base_url.rstrip("/") + path,
                json.dumps(body).encode(),headers=headers,method="POST")
            with urllib.request.urlopen(req,timeout=config.timeout_seconds) as response:
                payload=json.loads(response.read().decode())
            raw=payload["choices"][0]["message"]["content"]
            if isinstance(raw,list):
                raw="".join(x.get("text","") for x in raw if isinstance(x,dict))
            return validate_vision_result(_extract_json(raw))
        except urllib.error.HTTPError as e:
            last=e
            if e.code in (408,429,500,502,503,504) and attempt<config.max_retries:
                time.sleep(min(2**attempt,4)); continue
            raise VisionProviderUnavailable(f"{name} HTTP {e.code}") from e
        except (TimeoutError, urllib.error.URLError) as e:
            last=e
            if attempt<config.max_retries:
                time.sleep(min(2**attempt,4)); continue
            raise VisionProviderTimeout(f"{name} timed out/unavailable") from e
        except (KeyError, json.JSONDecodeError, VisionProviderProtocolError) as e:
            raise VisionProviderProtocolError(f"{name} invalid response") from e
    raise VisionProviderTimeout(f"{name} failed") from last

class FakeVisionProvider:
    modality="image"
    def __init__(self,name="fake-vision",confidence=.91): self.name=name; self.confidence=confidence; self.calls=0
    def analyse_images(self,request):
        self.calls += 1
        return VisionResult(.8,.7,.85,.75,.8,.8,False,False,[],["visible_scene"],
                             ["fake provider evidence"],self.confidence,self.name,0.0,0.0)

def build_configured_vision_providers():
    from .provider_config import load_provider_configs
    out=[]
    for config in load_provider_configs():
        if config.name in {"vision-cheap","vision-premium"} and config.enabled and config.base_url:
            out.append(OpenAICompatibleVisionProvider(config))
    return out

class AdaptiveVisionBrain:
    """Deterministic visual evidence first; paid image models only when justified."""
    VERSION="adaptive-vision-v1"
    def __init__(self, db, *, harness=None, registry=None, health=None,
                 deterministic=None, providers=None, required_confidence=.78):
        from .harness import Harness
        from .model_registry import ModelRegistry, register_configured_specs
        from .provider_health import ProviderHealth
        from .vision import VisionBrain
        self.db=db
        self.harness=harness or Harness(db)
        self.registry=registry or register_configured_specs(ModelRegistry())
        self.health=health or ProviderHealth()
        self.deterministic=deterministic or VisionBrain(db,max_frames=MAX_FRAMES)
        self.providers={p.name:p for p in (providers or [])}
        self.required_confidence=required_confidence

    def register_provider(self, provider): self.providers[provider.name]=provider

    def _key(self, request, model):
        frame_hashes=[(f.get("sha256",""),f.get("time")) for f in request.frames]
        raw=json.dumps({"v":self.VERSION,"task":request.task,"candidate":request.candidate_id,
                        "prompt":request.prompt_version,"model":model,"frames":frame_hashes,
                        "quality":request.quality_required},sort_keys=True)
        return "adaptive-vision:"+hashlib.sha256(raw.encode()).hexdigest()

    def _cached(self,key):
        row=self.db.get_artifact(key)
        if not row:return None
        try:return validate_vision_result(json.loads(row["metadata"])["result"])
        except Exception:return None

    def analyse(self, request):
        selected=self.deterministic.select_frames(request.frames)
        if not selected:
            return self.deterministic.analyse([],{"start":0,"end":0}), [{"stage":"deterministic","status":"no_frames"}]
        start=min(float(f["time"]) for f in selected)
        end=max(float(f["time"]) for f in selected)
        base=self.deterministic.analyse(selected,{"start":start,"end":end})
        trace=[{"stage":"deterministic","status":"executed","confidence":base.confidence}]
        if base.confidence >= request.quality_required:
            return base, trace
        remaining=request.budget_remaining
        for tier in ("cheap","premium"):
            spec=self.registry.choose("brain.vision",tier=tier,quality_required=request.quality_required,
                                      budget=remaining,modality="image")
            if not spec:
                trace.append({"stage":tier,"status":"blocked"})
                continue
            key=self._key(request,spec.name)
            cached=self._cached(key)
            if cached:
                trace.append({"stage":tier,"status":"cache_hit","model":spec.name})
                if cached.confidence >= request.quality_required:return cached,trace
                continue
            if not self.health.available(spec.name):
                trace.append({"stage":tier,"status":"health_blocked","model":spec.name}); continue
            provider=self.providers.get(spec.name)
            if not provider:
                trace.append({"stage":tier,"status":"adapter_missing","model":spec.name}); continue
            reservation=self.harness.budget.reserve(request.job_id,spec.estimated_cost,request.budget_remaining)
            try:
                result=provider.analyse_images(VisionRequest(
                    request.job_id,request.candidate_id,request.task,selected,
                    request.prompt_version,request.quality_required,remaining))
                result.estimated_cost=spec.estimated_cost
                self.harness.budget.settle(reservation,result.actual_cost or spec.estimated_cost)
            except (VisionProviderUnavailable,VisionProviderTimeout,VisionProviderProtocolError) as exc:
                self.harness.budget.release(reservation); self.health.failure(spec.name,exc)
                trace.append({"stage":tier,"status":"provider_failed","model":spec.name,"error":str(exc)})
                continue
            self.health.success(spec.name)
            self.db.put_artifact(key,"vision_provider_result","cache://"+key,key,{"result":result.to_dict()})
            remaining-=spec.estimated_cost
            trace.append({"stage":tier,"status":"executed","model":spec.name,"cost":spec.estimated_cost,
                          "confidence":result.confidence})
            if result.confidence >= request.quality_required:return result,trace
        return base,trace
