"""Capability Registry — canonical capability-facing interface.

Aggregates truth from existing components:
- model_registry (model capabilities)
- provider_config (provider configuration)
- provider_health (health state)
- vision_provider (vision capability)
- harness (runtime capabilities)

Answers: "What capabilities are actually available right now?"
"""
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class CapabilitySpec:
    capability_id: str
    status: str  # AVAILABLE, UNAVAILABLE, NOT_CONFIGURED, UNKNOWN, FAILED_HEALTH_CHECK
    provider: str
    implementation: str
    version: str
    requirements: list
    quality: float
    cost_class: str  # free, cheap, premium, unknown
    local: bool
    health: str
    last_verified: float
    supported_inputs: list
    supported_outputs: list
    constraints: dict


class CapabilityRegistry:
    """Canonical capability registry.

    Aggregates from existing components rather than duplicating them.
    """

    VERSION = "capability-registry-v1"

    # Known capabilities and their minimum requirements
    CAPABILITY_DEFS = {
        "transcription": {
            "implementation": "mlx-whisper",
            "requirements": ["mlx", "mlx_whisper"],
            "inputs": ["audio"],
            "outputs": ["transcript"],
            "quality": 0.85,
            "cost_class": "free",
            "local": True,
        },
        "vision": {
            "implementation": "vision_provider",
            "requirements": ["PIL"],
            "inputs": ["image"],
            "outputs": ["analysis"],
            "quality": 0.78,
            "cost_class": "cheap",
            "local": True,
        },
        "audio_analysis": {
            "implementation": "mlx-whisper",
            "requirements": ["mlx_whisper"],
            "inputs": ["audio"],
            "outputs": ["analysis"],
            "quality": 0.80,
            "cost_class": "free",
            "local": True,
        },
        "scene_analysis": {
            "implementation": "deterministic",
            "requirements": [],
            "inputs": ["frames"],
            "outputs": ["scene_data"],
            "quality": 0.70,
            "cost_class": "free",
            "local": True,
        },
        "screen_ocr": {
            "implementation": "pytesseract",
            "requirements": ["pytesseract", "PIL"],
            "inputs": ["frames"],
            "outputs": ["text"],
            "quality": 0.75,
            "cost_class": "free",
            "local": True,
        },
        "rendering": {
            "implementation": "ffmpeg",
            "requirements": ["ffmpeg"],
            "inputs": ["clips", "audio", "subtitles"],
            "outputs": ["video"],
            "quality": 0.90,
            "cost_class": "free",
            "local": True,
        },
        "qc": {
            "implementation": "semantic",
            "requirements": [],
            "inputs": ["script", "clips"],
            "outputs": ["qc_result"],
            "quality": 0.75,
            "cost_class": "free",
            "local": True,
        },
        "repair": {
            "implementation": "context_repair",
            "requirements": [],
            "inputs": ["qc_result"],
            "outputs": ["repaired"],
            "quality": 0.70,
            "cost_class": "free",
            "local": True,
        },
        "export": {
            "implementation": "review_manifest",
            "requirements": [],
            "inputs": ["clips", "qc"],
            "outputs": ["review_manifest"],
            "quality": 0.85,
            "cost_class": "free",
            "local": True,
        },
        "brain_reasoning": {
            "implementation": "deterministic_brain",
            "requirements": [],
            "inputs": ["candidate", "context"],
            "outputs": ["decision"],
            "quality": 0.62,
            "cost_class": "free",
            "local": True,
        },
    }

    def __init__(self, db=None, health=None, registry=None):
        self.db = db
        self.health = health
        self.model_registry = registry
        self._cache = None
        self._cache_time = 0
        self.CACHE_TTL = 30

    def inspect(self, force=False):
        """Return full capability registry. Cached unless force=True."""
        now = time.time()
        if self._cache is not None and (now - self._cache_time) < self.CACHE_TTL and not force:
            return self._cache

        capabilities = {}
        for cap_id, defn in self.CAPABILITY_DEFS.items():
            capabilities[cap_id] = self._evaluate_capability(cap_id, defn)

        # Add provider capabilities
        provider_caps = self._provider_capabilities()
        capabilities.update(provider_caps)

        self._cache = {
            "registry_version": self.VERSION,
            "generated_at": now,
            "capabilities": capabilities,
            "summary": self._summary(capabilities),
        }
        self._cache_time = now
        return self._cache

    def _evaluate_capability(self, cap_id, defn):
        """Evaluate a single capability against actual state."""
        # Check requirements
        missing_reqs = []
        for req in defn.get("requirements", []):
            try:
                __import__(req)
            except ImportError:
                missing_reqs.append(req)

        # Check health if available
        health_status = "HEALTHY"
        if self.health:
            health_status = self.health.state(cap_id)

        # Check model registry for provider-backed capabilities
        provider_available = None
        if self.model_registry and defn.get("provider"):
            specs = self.model_registry.for_capability(defn["provider"])
            provider_available = len(specs) > 0

        if missing_reqs:
            status = "UNAVAILABLE"
        elif health_status == "DEGRADED":
            status = "AVAILABLE_WITH_LIMITATIONS"
        elif provider_available is False:
            status = "NOT_CONFIGURED"
        else:
            status = "AVAILABLE"

        return {
            "capability_id": cap_id,
            "status": status,
            "provider": defn.get("implementation", "unknown"),
            "implementation": defn["implementation"],
            "version": self.VERSION,
            "requirements": defn.get("requirements", []),
            "quality": defn.get("quality", 0.0),
            "cost_class": defn.get("cost_class", "unknown"),
            "local": defn.get("local", True),
            "health": health_status,
            "last_verified": time.time(),
            "supported_inputs": defn.get("inputs", []),
            "supported_outputs": defn.get("outputs", []),
            "constraints": {},
        }

    def _provider_capabilities(self):
        """Get capabilities from configured providers."""
        caps = {}
        try:
            from clipping_farm.provider_config import load_provider_configs
            configs = load_provider_configs()
            for config in configs:
                if config.configured and config.enabled:
                    caps[f"provider_{config.name}"] = {
                        "capability_id": f"provider_{config.name}",
                        "status": "AVAILABLE",
                        "provider": config.name,
                        "implementation": "openai-compatible",
                        "version": "unknown",
                        "requirements": ["base_url"],
                        "quality": 0.90,
                        "cost_class": "premium" if "premium" in config.name else "cheap",
                        "local": False,
                        "health": "HEALTHY",
                        "last_verified": time.time(),
                        "supported_inputs": ["text", "image"],
                        "supported_outputs": ["analysis", "decision"],
                        "constraints": {},
                    }
        except Exception:
            pass
        return caps

    def _summary(self, capabilities):
        """Generate summary counts."""
        total = len(capabilities)
        available = sum(1 for c in capabilities.values() if c["status"] == "AVAILABLE")
        degraded = sum(1 for c in capabilities.values() if c["status"] == "AVAILABLE_WITH_LIMITATIONS")
        unavailable = sum(1 for c in capabilities.values() if c["status"] == "UNAVAILABLE")
        not_configured = sum(1 for c in capabilities.values() if c["status"] == "NOT_CONFIGURED")
        return {
            "total": total,
            "available": available,
            "degraded": degraded,
            "unavailable": unavailable,
            "not_configured": not_configured,
        }

    def get_capability(self, capability_id):
        """Query a single capability."""
        caps = self.inspect()["capabilities"]
        return caps.get(capability_id)

    def for_task(self, task):
        """Return capabilities relevant to a task."""
        caps = self.inspect()["capabilities"]
        task_map = {
            "transcribe": ["transcription"],
            "analyse_scenes": ["scene_analysis"],
            "analyse_screen_text": ["screen_ocr", "vision"],
            "generate_candidates": ["brain_reasoning"],
            "score_candidates": ["brain_reasoning"],
            "qc": ["qc"],
            "repair": ["repair"],
            "export_review": ["export"],
        }
        needed = task_map.get(task, [])
        return {k: v for k, v in caps.items() if k in needed}

    def choose_provider(self, capability, quality_required=0.0, budget=0.0):
        """Choose the best provider for a capability."""
        specs = []
        if self.model_registry:
            specs = self.model_registry.for_capability(capability)

        # Filter by quality and budget
        affordable = [s for s in specs if s.estimated_cost <= budget and s.quality >= quality_required]
        if affordable:
            return sorted(affordable, key=lambda s: (s.estimated_cost, -s.quality))[0]

        # Fall back to deterministic/local
        local_specs = [s for s in specs if s.tier == "deterministic"]
        if local_specs:
            return local_specs[0]

        return None


def get_registry(db=None, health=None, registry=None, force=False):
    """Convenience function: return registry dict."""
    return CapabilityRegistry(db=db, health=health, registry=registry).inspect(force=force)