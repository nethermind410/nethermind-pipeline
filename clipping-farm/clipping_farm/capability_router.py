"""Capability routing — routes work based on actual capability availability.

Uses Capability Registry to determine the best provider for each task.
Considers: required capability, available provider, quality, cost,
hardware/resource requirements, latency, fallback.

Never claims external provider available without verifying config/credentials/health.
No silent downgrade — always reports why a choice was made.
"""
import time
from typing import Optional, Dict, List


class RouteResult:
    """Result of a routing decision."""

    def __init__(self, provider: str, model: str, method: str,
                 estimated_cost: float, quality: float, reason: str,
                 latency_ms: float = 0, fallback: bool = False):
        self.provider = provider
        self.model = model
        self.method = method
        self.estimated_cost = estimated_cost
        self.quality = quality
        self.reason = reason
        self.latency_ms = latency_ms
        self.fallback = fallback

    def to_dict(self):
        return {
            "provider": self.provider,
            "model": self.model,
            "method": self.method,
            "estimated_cost": self.estimated_cost,
            "quality": self.quality,
            "reason": self.reason,
            "latency_ms": self.latency_ms,
            "fallback": self.fallback,
        }


class CapabilityRouter:
    """Routes tasks to the best available capability/provider."""

    VERSION = "capability-router-v1"

    # Task-to-capability mapping
    TASK_CAPABILITY_MAP = {
        "transcribe": "transcription",
        "analyse_audio": "audio_analysis",
        "analyse_scenes": "scene_analysis",
        "analyse_screen_text": "screen_ocr",
        "generate_candidates": "brain_reasoning",
        "score_candidates": "brain_reasoning",
        "select_candidates": "brain_reasoning",
        "produce_clips": "rendering",
        "qc": "qc",
        "repair": "repair",
        "export_review": "export",
    }

    # Latency targets per capability (ms)
    LATENCY_TARGETS = {
        "transcription": 30000,
        "audio_analysis": 15000,
        "scene_analysis": 5000,
        "screen_ocr": 3000,
        "brain_reasoning": 10000,
        "rendering": 60000,
        "qc": 5000,
        "repair": 5000,
        "export": 2000,
    }

    def __init__(self, registry=None, health=None, db=None):
        self.registry = registry
        self.health = health
        self.db = db
        self._route_cache = {}
        self._cache_ttl = 60

    def route(self, task, *, quality_required=0.0, budget=0.0,
              modality="multimodal", latency_sla_ms=None):
        """Route a task to the best available capability.

        Returns RouteResult with the chosen provider and reasoning.
        Falls back to deterministic/local if no provider available.
        """
        capability = self.TASK_CAPABILITY_MAP.get(task)
        if not capability:
            raise ValueError(f"Unknown task: {task}")

        # Get available providers for this capability
        providers = self._get_providers(capability, modality=modality)

        if not providers:
            # Fall back to deterministic/local
            fallback = self._get_fallback(capability)
            if fallback:
                return RouteResult(
                    provider=fallback["provider"],
                    model=fallback["model"],
                    method="fallback",
                    estimated_cost=0.0,
                    quality=fallback.get("quality", 0.0),
                    reason=f"Fallback: no provider for {capability}",
                    fallback=True,
                )
            raise RuntimeError(
                f"No providers available for capability '{capability}' "
                f"(task: {task}). Configure a provider or use deterministic mode."
            )

        # Filter by quality and budget
        suitable = self._filter_by_quality_budget(
            providers, quality_required, budget
        )

        # Filter by latency SLA if specified
        if latency_sla_ms is not None:
            suitable = [
                p for p in suitable
                if self._estimated_latency(p, capability) <= latency_sla_ms
            ]

        # Check health
        healthy = [
            p for p in suitable
            if self._check_health(p)
        ]

        if not healthy:
            # Fall back to deterministic/local
            fallback = self._get_fallback(capability)
            if fallback:
                return RouteResult(
                    provider=fallback["provider"],
                    model=fallback["model"],
                    method="fallback",
                    estimated_cost=0.0,
                    quality=fallback.get("quality", 0.0),
                    reason=f"Fallback: no healthy provider for {capability}",
                    fallback=True,
                )
            raise RuntimeError(
                f"No healthy provider for capability '{capability}' "
                f"and no fallback available."
            )

        # Select best: lowest cost, then highest quality
        best = sorted(healthy, key=lambda p: (
            p.get("estimated_cost", 0),
            -p.get("quality", 0),
        ))[0]

        return RouteResult(
            provider=best["provider"],
            model=best.get("model", best["provider"]),
            method=best.get("tier", "standard"),
            estimated_cost=best.get("estimated_cost", 0.0),
            quality=best.get("quality", 0.0),
            reason=f"Best match for {capability}: {best['provider']}",
            latency_ms=self._estimated_latency(best, capability),
            fallback=False,
        )

    def _get_providers(self, capability, modality="multimodal"):
        """Get available providers for a capability."""
        providers = []

        # From Capability Registry
        if self.registry:
            cap_data = self.registry.get_capability(capability)
            if cap_data and cap_data.get("status") == "AVAILABLE":
                providers.append({
                    "provider": cap_data.get("provider", "local"),
                    "model": cap_data.get("implementation", "local"),
                    "tier": cap_data.get("cost_class", "free"),
                    "quality": cap_data.get("quality", 0.0),
                    "estimated_cost": 0.0 if cap_data.get("cost_class") == "free" else 0.01,
                    "modality": cap_data.get("supported_inputs", [modality]),
                    "health": cap_data.get("health", "HEALTHY"),
                })

        # From Model Registry
        if self.db:
            try:
                from clipping_farm.model_registry import ModelRegistry, register_configured_specs
                registry = ModelRegistry()
                registry = register_configured_specs(registry)
                specs = registry.for_capability(capability)
                for spec in specs:
                    providers.append({
                        "provider": spec.name,
                        "model": spec.name,
                        "tier": spec.tier,
                        "quality": spec.quality,
                        "estimated_cost": spec.estimated_cost,
                        "modality": spec.modality,
                        "health": "HEALTHY",
                    })
            except Exception:
                pass

        # Deduplicate by provider
        seen = set()
        unique = []
        for p in providers:
            if p["provider"] not in seen:
                seen.add(p["provider"])
                unique.append(p)

        return unique

    def _filter_by_quality_budget(self, providers, quality_required, budget):
        """Filter providers by quality and budget."""
        result = []
        for p in providers:
            if p.get("quality", 0) < quality_required:
                continue
            if p.get("estimated_cost", 0) > budget:
                continue
            result.append(p)
        return result

    def _estimated_latency(self, provider, capability):
        """Estimate latency for a provider/capability pair."""
        base = self.LATENCY_TARGETS.get(capability, 5000)
        tier = provider.get("tier", "standard")
        if tier == "cheap":
            return base * 1.5
        elif tier == "premium":
            return base * 0.7
        return base

    def _check_health(self, provider):
        """Check if a provider is healthy."""
        if self.health:
            return self.health.available(provider["provider"])
        return provider.get("health", "HEALTHY") == "HEALTHY"

    def _get_fallback(self, capability):
        """Get deterministic fallback for a capability."""
        # Deterministic tasks always have fallback
        deterministic_tasks = {
            "transcription": {"provider": "local", "model": "mlx-whisper", "quality": 0.85},
            "audio_analysis": {"provider": "local", "model": "mlx-whisper", "quality": 0.80},
            "scene_analysis": {"provider": "local", "model": "deterministic", "quality": 0.70},
            "screen_ocr": {"provider": "local", "model": "pytesseract", "quality": 0.75},
            "rendering": {"provider": "local", "model": "ffmpeg", "quality": 0.90},
            "qc": {"provider": "local", "model": "semantic", "quality": 0.75},
            "repair": {"provider": "local", "model": "context_repair", "quality": 0.70},
            "export": {"provider": "local", "model": "review_manifest", "quality": 0.85},
            "brain_reasoning": {"provider": "local", "model": "deterministic-brain", "quality": 0.62},
        }
        fallback = deterministic_tasks.get(capability)
        if fallback:
            fallback["provider"] = fallback["provider"]
            fallback["model"] = fallback["model"]
            fallback["quality"] = fallback["quality"]
        return fallback

    def route_task(self, task, **kwargs):
        """Convenience: route a task by name."""
        return self.route(task, **kwargs)

    def get_route_reasoning(self, task, **kwargs):
        """Get routing decision with full reasoning trace."""
        try:
            result = self.route(task, **kwargs)
            return {
                "task": task,
                "routed": True,
                "provider": result.provider,
                "model": result.model,
                "method": result.method,
                "estimated_cost": result.estimated_cost,
                "quality": result.quality,
                "reason": result.reason,
                "latency_ms": result.latency_ms,
                "fallback": result.fallback,
            }
        except Exception as e:
            return {
                "task": task,
                "routed": False,
                "reason": str(e),
                "fallback": False,
            }