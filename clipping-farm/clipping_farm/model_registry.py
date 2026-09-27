"""Capability-based model registry used by the Harness.

Models are registered by capability rather than hard-coded into agents. The
default registry is offline-safe: deterministic/local entries cost zero and
mock paid tiers are only used by tests until real adapters are installed.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ModelSpec:
    name: str
    capability: str
    modality: str
    tier: str
    estimated_cost: float
    quality: float
    speed: float
    available: bool = True
    limits: Dict[str, object] = field(default_factory=dict)


class ModelRegistry:
    def __init__(self, specs: Optional[List[ModelSpec]] = None):
        self._specs: Dict[str, ModelSpec] = {}
        for spec in specs or default_specs():
            self.register(spec)

    def register(self, spec: ModelSpec) -> None:
        self._specs[spec.name] = spec

    def get(self, name: str) -> Optional[ModelSpec]:
        return self._specs.get(name)

    def for_capability(self, capability: str, *, tier: Optional[str] = None,
                       modality: Optional[str] = None) -> List[ModelSpec]:
        rows = [
            s for s in self._specs.values()
            if s.capability == capability and s.available
            and (tier is None or s.tier == tier)
            and (modality is None or s.modality == modality)
        ]
        return sorted(rows, key=lambda s: (-s.quality, s.estimated_cost, -s.speed))

    def choose(self, capability: str, *, quality_required: float = 0.0,
               budget: float = 0.0, modality: Optional[str] = None) -> Optional[ModelSpec]:
        rows = self.for_capability(capability, modality=modality)
        affordable = [s for s in rows if s.estimated_cost <= budget and s.quality >= quality_required]
        if affordable:
            return sorted(affordable, key=lambda s: (s.estimated_cost, -s.quality))[0]
        return None


def default_specs() -> List[ModelSpec]:
    return [
        ModelSpec("deterministic-local", "brain.reasoning", "multimodal", "deterministic", 0.0, 0.62, 1.0),
        ModelSpec("cheap-mock", "brain.reasoning", "multimodal", "cheap", 0.005, 0.84, 0.85),
        ModelSpec("premium-mock", "brain.reasoning", "multimodal", "premium", 0.05, 0.96, 0.55),
    ]
