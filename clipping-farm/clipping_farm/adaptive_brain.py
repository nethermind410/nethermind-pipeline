"""Brain orchestration: deterministic first, then bounded capability escalation."""
from dataclasses import dataclass, field
import json

from .evidence import EvidencePacket
from .harness import Harness
from .model_registry import ModelRegistry
from .providers import BrainProvider, ProviderResult
from .provider_contracts import validate_packet, validate_result
from .provider_health import ProviderHealth
from .provider_adapters import ProviderUnavailable, ProviderTimeout, ProviderProtocolError


@dataclass
class AdaptiveResult:
    result: ProviderResult
    trace: list = field(default_factory=list)
    blocked: bool = False


class AdaptiveBrain:
    def __init__(self, db, *, harness=None, registry=None, providers=None,
                 required_confidence=0.78, health=None):
        self.db = db
        self.harness = harness or Harness(db)
        self.registry = registry or ModelRegistry()
        self.providers = providers or {}
        self.required_confidence = required_confidence
        self.health = health or ProviderHealth()

    def register_provider(self, provider: BrainProvider):
        self.providers[provider.name] = provider

    def _cache_key(self, task, model, digest):
        return self.harness.router.cache_key(task, self.required_confidence, digest,
                                             "multimodal", model)

    def _cached(self, key):
        row = self.db.get_artifact(key)
        if not row:
            return None
        try:
            return ProviderResult(**json.loads(row["metadata"])["provider_result"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def _store(self, key, result):
        payload = {"provider_result": {
            "decision": result.decision,
            "confidence": result.confidence,
            "reason": result.reason,
            "evidence": result.evidence,
            "scores": result.scores,
            "model": result.model,
            "estimated_cost": result.estimated_cost,
            "actual_cost": result.actual_cost,
        }}
        self.db.put_artifact(key, "brain_provider_result", f"cache://{key}",
                             key, payload)

    def _run_paid(self, provider_name, packet, *, job_id, budget, total_budget, trace):
        spec = self.registry.get(provider_name)
        if not spec or not spec.available:
            trace.append({"model": provider_name, "status": "unavailable"})
            return None, budget
        if spec.estimated_cost > budget:
            trace.append({"model": provider_name, "status": "budget_blocked",
                          "cost": spec.estimated_cost, "remaining": budget})
            return None, budget

        key = self._cache_key("brain_provider", provider_name, packet.digest())
        cached = self._cached(key)
        if cached:
            trace.append({"model": provider_name, "status": "cache_hit"})
            return cached, budget

        if not self.health.available(provider_name):
            trace.append({"model": provider_name, "status": "health_blocked"})
            return None, budget
        provider = self.providers.get(provider_name)
        if provider is None:
            trace.append({"model": provider_name, "status": "adapter_missing"})
            return None, budget

        reservation_id = self.harness.budget.reserve(job_id, spec.estimated_cost, total_budget)
        try:
            result = provider.analyse(packet)
            validate_result({"decision": result.decision, "confidence": result.confidence, "reason": result.reason, "evidence": result.evidence, "scores": result.scores, "model": result.model})
            result.estimated_cost = spec.estimated_cost
            self.harness.budget.settle(reservation_id, result.actual_cost or spec.estimated_cost)
        except (ProviderUnavailable, ProviderTimeout, ProviderProtocolError) as exc:
            self.harness.budget.release(reservation_id)
            self.health.failure(provider_name, exc)
            trace.append({"model": provider_name, "status": "provider_failed", "error": str(exc)})
            return None, budget
        except Exception:
            self.harness.budget.release(reservation_id)
            raise
        self.health.success(provider_name)
        self._store(key, result)
        trace.append({"model": provider_name, "status": "executed",
                      "cost": spec.estimated_cost})
        return result, budget - spec.estimated_cost

    def analyse(self, packet: EvidencePacket, *, job_id="brain", budget=0.0):
        validate_packet(packet.to_dict())
        trace = [{"model": "deterministic", "status": "executed"}]
        deterministic = self.providers.get("deterministic")
        if deterministic is None:
            raise RuntimeError("deterministic provider is required")
        result = deterministic.analyse(packet)
        validate_result({"decision": result.decision, "confidence": result.confidence, "reason": result.reason, "evidence": result.evidence, "scores": result.scores, "model": result.model})

        if result.confidence >= self.required_confidence and not self._needs_escalation(result):
            return AdaptiveResult(result, trace)

        cheap = self.registry.choose("brain.reasoning", tier="cheap",
                                     quality_required=0.70, budget=budget,
                                     modality="multimodal")
        if cheap is None:
            trace.append({"status": "escalation_blocked", "reason": "no affordable cheap model"})
            return AdaptiveResult(result, trace, blocked=True)

        result2, remaining = self._run_paid(cheap.name, packet, job_id=job_id,
                                            budget=budget, total_budget=budget, trace=trace)
        if result2 and result2.confidence >= self.required_confidence:
            return AdaptiveResult(result2, trace)

        premium = self.registry.choose("brain.reasoning", tier="premium",
                                       quality_required=self.required_confidence,
                                       budget=remaining, modality="multimodal")
        if premium is None:
            trace.append({"status": "escalation_blocked", "reason": "premium budget unavailable"})
            return AdaptiveResult(result2 or result, trace, blocked=True)

        result3, _ = self._run_paid(premium.name, packet, job_id=job_id,
                                     budget=remaining, total_budget=budget, trace=trace)
        return AdaptiveResult(result3 or result2 or result, trace, blocked=result3 is None)

    @staticmethod
    def _needs_escalation(result):
        return bool(getattr(result, "escalate", False)) or result.confidence < 0.78
