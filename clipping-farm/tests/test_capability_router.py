"""Tests for Capability Router (Phase 6)."""
import pytest
from clipping_farm.capability_router import CapabilityRouter, RouteResult
from clipping_farm.capability_registry import CapabilityRegistry
from clipping_farm.provider_health import ProviderHealth
from clipping_farm.db import DB
import tempfile


class TestCapabilityRouter:
    @pytest.fixture
    def db(self):
        f = tempfile.NamedTemporaryFile(suffix=".db")
        return DB(f.name)

    def test_router_init(self, db):
        router = CapabilityRouter(db=db)
        assert router.VERSION == "capability-router-v1"

    def test_route_transcribe(self, db):
        registry = CapabilityRegistry(db=db)
        router = CapabilityRouter(registry=registry, db=db)
        result = router.route("transcribe")
        assert isinstance(result, RouteResult)
        assert result.provider is not None

    def test_route_unknown_task(self, db):
        router = CapabilityRouter(db=db)
        with pytest.raises(ValueError):
            router.route("unknown_task")

    def test_route_no_providers(self, db):
        router = CapabilityRouter(db=db)
        # brain_reasoning has no providers; deterministic fallback available
        result = router.route("generate_candidates")
        assert result is not None
        assert result.fallback is True

    def test_route_with_quality_required(self, db):
        registry = CapabilityRegistry(db=db)
        router = CapabilityRouter(registry=registry, db=db)
        result = router.route("transcribe", quality_required=0.9)
        assert result is not None

    def test_route_with_budget(self, db):
        registry = CapabilityRegistry(db=db)
        router = CapabilityRouter(registry=registry, db=db)
        result = router.route("transcribe", budget=0.01)
        assert result is not None

    def test_route_zero_budget_no_fallback(self, db):
        registry = CapabilityRegistry(db=db)
        router = CapabilityRouter(registry=registry, db=db)
        result = router.route("generate_candidates", budget=0.0)
        # Should use fallback (deterministic/local)
        assert result.fallback is True or result.method == "fallback" or result.estimated_cost == 0.0

    def test_route_with_latency_sla(self, db):
        registry = CapabilityRegistry(db=db)
        router = CapabilityRouter(registry=registry, db=db)
        result = router.route("transcribe", latency_sla_ms=10000)
        assert result is not None

    def test_route_with_modality(self, db):
        registry = CapabilityRegistry(db=db)
        router = CapabilityRouter(registry=registry, db=db)
        result = router.route("transcribe", modality="audio")
        assert result is not None

    def test_get_providers(self, db):
        registry = CapabilityRegistry(db=db)
        router = CapabilityRouter(registry=registry, db=db)
        providers = router._get_providers("transcription")
        assert isinstance(providers, list)

    def test_filter_by_quality_budget(self, db):
        registry = CapabilityRegistry(db=db)
        router = CapabilityRouter(registry=registry, db=db)
        providers = router._get_providers("transcription")
        filtered = router._filter_by_quality_budget(providers, 0.5, 1.0)
        assert isinstance(filtered, list)

    def test_get_fallback(self, db):
        registry = CapabilityRegistry(db=db)
        router = CapabilityRouter(registry=registry, db=db)
        fallback = router._get_fallback("transcription")
        assert fallback is not None
        assert "provider" in fallback

    def test_get_fallback_unknown(self, db):
        registry = CapabilityRegistry(db=db)
        router = CapabilityRouter(registry=registry, db=db)
        fallback = router._get_fallback("nonexistent")
        assert fallback is None

    def test_route_task_convenience(self, db):
        registry = CapabilityRegistry(db=db)
        router = CapabilityRouter(registry=registry, db=db)
        result = router.route_task("transcribe")
        assert isinstance(result, RouteResult)

    def test_get_route_reasoning_success(self, db):
        registry = CapabilityRegistry(db=db)
        router = CapabilityRouter(registry=registry, db=db)
        reasoning = router.get_route_reasoning("transcribe")
        assert reasoning["routed"] is True
        assert "reason" in reasoning

    def test_get_route_reasoning_unknown_task(self, db):
        router = CapabilityRouter(db=db)
        reasoning = router.get_route_reasoning("unknown_task")
        assert reasoning["routed"] is False

    def test_route_health_check(self, db):
        health = ProviderHealth()
        health.failure("bad-provider", "test error")
        registry = CapabilityRegistry(db=db)
        router = CapabilityRouter(registry=registry, health=health, db=db)
        # Healthy providers should still route
        result = router.route("transcribe")
        assert result is not None

    def test_version(self, db):
        router = CapabilityRouter(db=db)
        assert router.VERSION == "capability-router-v1"

    def test_latency_targets(self, db):
        registry = CapabilityRegistry(db=db)
        router = CapabilityRouter(registry=registry, db=db)
        result = router.route("transcribe")
        assert result.latency_ms > 0

    def test_route_qc(self, db):
        registry = CapabilityRegistry(db=db)
        router = CapabilityRouter(registry=registry, db=db)
        result = router.route("qc")
        assert isinstance(result, RouteResult)

    def test_route_export(self, db):
        registry = CapabilityRegistry(db=db)
        router = CapabilityRouter(registry=registry, db=db)
        result = router.route("export_review")
        assert isinstance(result, RouteResult)