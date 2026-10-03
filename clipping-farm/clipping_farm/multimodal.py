"""Multimodal candidate fusion.

Combines modality-specific evidence without treating any missing modality as
positive evidence. Fusion is deterministic and explainable; external models
may refine it later through the provider layer.
"""
from dataclasses import dataclass, asdict
import hashlib, json

@dataclass
class FusionResult:
    decision: str
    confidence: float
    scores: dict
    evidence: list
    missing_modalities: list
    reason: str

    def to_dict(self):
        return asdict(self)

    def digest(self):
        return hashlib.sha256(
            json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()


class MultimodalCandidateBrain:
    VERSION = "fusion-v1"

    WEIGHTS = {
        "hook": .16,
        "payoff": .16,
        "context": .12,
        "standalone": .18,
        "information": .12,
        "novelty": .08,
        "visual": .10,
        "audio": .08,
    }

    def analyse(self, candidate, *, visual=None, audio=None, transcript=None,
                context=None):
        base = dict(candidate.get("scores", {}))
        scores = {}
        evidence = []
        missing = []

        for key in ("hook", "payoff", "context", "standalone",
                    "information", "novelty"):
            if key in base:
                scores[key] = self._clamp(base[key])
            else:
                missing.append(key)
        if audio and "peak" in audio:
            scores["audio"] = 1.0 if float(audio["peak"]) >= .03 else .6
            evidence.append("audio peak evidence supplied")
        else:
            missing.append("audio")

        if visual is not None:
            visual_parts = [("composition", .15), ("action", .20), ("subject_visibility", .20), ("visual_novelty", .15), ("relevance", .20), ("continuity", .10)]
            supplied = [(key, weight, self._clamp(visual[key])) for key, weight in visual_parts if key in visual]
            denom = sum(weight for _, weight, _ in supplied)
            scores["visual"] = sum(weight * value for _, weight, value in supplied) / denom if denom else 0.0
            # Preserve richer visual evidence for downstream QC.
            evidence.extend(visual.get("evidence", []))
        else:
            missing.append("visual")

        if context:
            if context.get("reasons"):
                evidence.extend(context["reasons"])
            if "score" in context and "context" not in scores:
                scores["context"] = self._clamp(context["score"])
                if "context" in missing:
                    missing.remove("context")

        available_weights = [(k, w) for k, w in self.WEIGHTS.items() if k in scores]
        # If visual evidence is invalid (no frames), exclude visual weight
        # so it doesn't drag down the total
        visual_bad = "no_valid_frames" in evidence
        if visual_bad and "visual" in dict(available_weights):
            available_weights = [(k, w) for k, w in available_weights if k != "visual"]
        denominator = sum(w for _, w in available_weights)
        total = float(sum(scores[k] * w for k, w in available_weights) / denominator
                 if denominator else 0.0)

        # Missing modalities reduce confidence rather than lowering the actual
        # observed score. This distinguishes "bad evidence" from "no evidence".
        completeness = len(available_weights) / len(self.WEIGHTS)
        confidence = float(max(0.0, min(0.99, total * (0.65 + .35 * completeness))))

        standalone = scores.get("standalone", 0.0)
        audio_score = scores.get("audio", 0.0)
        audio_strong = audio_score >= 0.8
        multimodal_ok = total >= .62 and standalone >= .65 and completeness >= .75
        audio_only_ok = standalone >= .65 and total >= .40 and audio_strong and completeness >= .625
        decision = "accept" if (multimodal_ok or audio_only_ok) else "review" if standalone >= .50 and total >= .50 else "reject"

        if not evidence:
            evidence.append("no positive supporting evidence beyond numeric scores")

        reason = (
            "multimodal evidence meets acceptance gates"
            if decision == "accept"
            else "insufficient multimodal evidence for automatic acceptance"
            if decision == "review"
            else "candidate fails multimodal acceptance gates"
        )
        return FusionResult(
            decision=decision,
            confidence=round(confidence, 3),
            scores={k: round(v, 3) for k, v in scores.items()},
            evidence=evidence,
            missing_modalities=sorted(set(missing)),
            reason=reason,
        )

    @staticmethod
    def _clamp(value):
        return max(0.0, min(1.0, float(value)))
