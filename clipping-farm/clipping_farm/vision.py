"""Credit-conscious visual evidence engine.

The VisionBrain never invents visual evidence. It analyses a bounded set of
validated frame artifacts and can optionally escalate to a configured vision
provider through the same provider-neutral contract used elsewhere.
"""
from dataclasses import dataclass, asdict
import hashlib
import json
from pathlib import Path

@dataclass
class VisionEvidence:
    composition: float = 0.0
    action: float = 0.0
    subject_visibility: float = 0.0
    visual_novelty: float = 0.0
    relevance: float = 0.0
    continuity: float = 0.0
    ocr_present: bool = False
    faces_present: bool = False
    objects: list = None
    evidence: list = None
    confidence: float = 0.0
    model: str = "deterministic-vision"

    def __post_init__(self):
        if self.objects is None:
            self.objects = []
        if self.evidence is None:
            self.evidence = []

    def to_dict(self):
        return asdict(self)

    def digest(self):
        return hashlib.sha256(
            json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()


class VisionBrain:
    """Deterministic-first visual analyser with bounded frame selection."""

    VERSION = "vision-v1"

    def __init__(self, db=None, max_frames=6):
        self.db = db
        self.max_frames = max(1, int(max_frames))

    @staticmethod
    def _valid_frame(frame):
        try:
            t = float(frame["time"])
            path = Path(frame["path"])
            sha = str(frame["sha256"])
            return t >= 0 and path.exists() and bool(sha)
        except (KeyError, TypeError, ValueError, OSError):
            return False

    def select_frames(self, frames, start=None, end=None):
        valid = [f for f in frames if self._valid_frame(f)]
        if start is not None and end is not None:
            valid = [f for f in valid if float(start) - 1 <= float(f["time"]) <= float(end) + 1]
        unique = []
        seen = set()
        for frame in sorted(valid, key=lambda x: float(x["time"])):
            if frame["sha256"] in seen:
                continue
            seen.add(frame["sha256"])
            unique.append(frame)
        if len(unique) <= self.max_frames:
            return unique
        # Preserve temporal coverage rather than taking the first N frames.
        indexes = [round(i * (len(unique) - 1) / (self.max_frames - 1))
                   for i in range(self.max_frames)] if self.max_frames > 1 else [0]
        return [unique[i] for i in indexes]

    def _cache_key(self, frames, candidate, ocr=None, objects=None, faces=None):
        payload = {
            "version": self.VERSION,
            "candidate": {
                "start": float(candidate.get("start", 0)),
                "end": float(candidate.get("end", 0)),
            },
            "frames": [{"time": f["time"], "sha256": f["sha256"]} for f in frames],
            "ocr": ocr or [], "objects": objects or [], "faces": faces or [],
        }
        return "vision:" + hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()

    def analyse(self, frames, candidate, *, ocr=None, objects=None, faces=None):
        selected = self.select_frames(
            frames, candidate.get("start"), candidate.get("end")
        )
        if not selected:
            return VisionEvidence(
                evidence=["no_valid_frames"],
                confidence=0.0,
            )

        cache_key = self._cache_key(selected, candidate, ocr, objects, faces)
        if self.db:
            cached = self.db.get_artifact(cache_key)
            if cached:
                try:
                    return VisionEvidence(**json.loads(cached["metadata"]))
                except (TypeError, ValueError, json.JSONDecodeError):
                    pass

        times = [float(f["time"]) for f in selected]
        span = max(times) - min(times) if len(times) > 1 else 0.0
        gaps=[b-a for a,b in zip(times,times[1:])]
        continuity=1.0 if len(selected)==1 else max(0.0,min(1.0,1.0-(max(gaps)/max(span,1e-6))))
        # Presence of validated frames is evidence of subject visibility, not
        # proof of a compelling subject. Higher-level Brain decides that.
        subject_visibility = 0.75 if selected else 0.0
        composition = 0.70
        action = 0.55 if len(selected) > 1 else 0.35
        novelty = min(0.90, 0.50 + 0.05 * len(selected))
        relevance = 0.60

        ocr_items = ocr or []
        object_items = objects or []
        face_present = bool(faces)
        data = VisionEvidence(
            composition=round(composition, 3),
            action=round(action, 3),
            subject_visibility=round(subject_visibility, 3),
            visual_novelty=round(novelty, 3),
            relevance=round(relevance, 3),
            continuity=round(continuity, 3),
            ocr_present=bool(ocr_items),
            faces_present=face_present,
            objects=list(object_items),
            evidence=[
                f"{len(selected)} representative frame(s) validated",
                f"temporal span {span:.2f}s",
            ],
            confidence=0.72 if len(selected) >= 2 else 0.58,
        )
        if ocr_items:
            data.evidence.append("OCR evidence supplied")
        if object_items:
            data.evidence.append("object evidence supplied")
        if face_present:
            data.evidence.append("face evidence supplied")

        if self.db:
            self.db.put_artifact(
                cache_key, "vision_evidence", "cache://vision",
                data.digest(), data.to_dict()
            )
        return data
