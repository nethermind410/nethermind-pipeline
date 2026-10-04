"""Tests for System Manifest and Capability Registry."""
import pytest
from clipping_farm.system_manifest import SystemManifest
from clipping_farm.capability_registry import CapabilityRegistry


class TestSystemManifest:
    @pytest.fixture
    def manifest(self):
        return SystemManifest()

    def test_inspect_returns_dict(self, manifest):
        result = manifest.inspect()
        assert isinstance(result, dict)
        assert "manifest_version" in result
        assert result["manifest_version"] == "manifest-v1"
        assert "generated_at" in result

    def test_inspect_has_runtime(self, manifest):
        result = manifest.inspect()
        runtime = result["runtime"]
        assert "pid" in runtime
        assert "cwd" in runtime

    def test_inspect_has_os(self, manifest):
        result = manifest.inspect()
        os_info = result["os"]
        assert "system" in os_info
        assert "release" in os_info

    def test_inspect_has_python(self, manifest):
        result = manifest.inspect()
        py = result["python"]
        assert "version" in py
        assert "executable" in py

    def test_inspect_has_ffmpeg(self, manifest):
        result = manifest.inspect()
        ff = result["ffmpeg"]
        assert "installed" in ff
        assert "version" in ff

    def test_inspect_has_ml(self, manifest):
        result = manifest.inspect()
        ml = result["ml"]
        assert "mlx" in ml
        assert "whisper" in ml
        assert "torch" in ml

    def test_inspect_has_providers(self, manifest):
        result = manifest.inspect()
        assert "providers" in result
        assert isinstance(result["providers"], list)

    def test_inspect_has_models(self, manifest):
        result = manifest.inspect()
        assert "models" in result
        assert isinstance(result["models"], list)

    def test_inspect_has_storage(self, manifest):
        result = manifest.inspect()
        storage = result["storage"]
        assert "free_gb" in storage or "error" in storage

    def test_inspect_has_capabilities(self, manifest):
        result = manifest.inspect()
        caps = result["capabilities"]
        assert isinstance(caps, dict)
        assert "transcription" in caps
        assert "rendering" in caps

    def test_inspect_has_capability_keys(self, manifest):
        result = manifest.inspect()
        caps = result["capabilities"]
        for cap_name, cap_data in caps.items():
            assert "available" in cap_data or "status" in cap_data

    def test_get_capability_returns_cap(self, manifest):
        cap = manifest.get_capability("transcription")
        assert cap is not None
        assert "available" in cap or "status" in cap

    def test_get_capability_unknown_returns_false(self, manifest):
        cap = manifest.get_capability("nonexistent_capability")
        assert cap is not None
        assert cap.get("available") is False or cap.get("status") == "UNKNOWN"

    def test_all_available_returns_list(self, manifest):
        result = manifest.all_available()
        assert isinstance(result, list)
        # At least some capabilities should be available
        assert len(result) >= 1

    def test_inspect_caches_result(self, manifest):
        r1 = manifest.inspect()
        r2 = manifest.inspect()
        # Same object returned (cached)
        assert r1 is r2

    def test_inspect_force_bypasses_cache(self, manifest):
        r1 = manifest.inspect()
        r2 = manifest.inspect(force=True)
        # Different objects but same content
        assert r1["manifest_version"] == r2["manifest_version"]

    def test_to_dict_returns_manifest(self, manifest):
        result = manifest.to_dict()
        assert isinstance(result, dict)
        assert result == manifest.inspect()

    def test_cache_expires(self, manifest):
        manifest.CACHE_TTL = 0  # expire immediately
        r1 = manifest.inspect()
        r2 = manifest.inspect()
        # Cache expired, new result
        assert r1 is not r2


class TestCapabilityRegistry:
    @pytest.fixture
    def registry(self):
        return CapabilityRegistry()

    def test_inspect_returns_dict(self, registry):
        result = registry.inspect()
        assert isinstance(result, dict)
        assert "registry_version" in result
        assert result["registry_version"] == "capability-registry-v1"
        assert "generated_at" in result

    def test_inspect_has_capabilities(self, registry):
        result = registry.inspect()
        caps = result["capabilities"]
        assert isinstance(caps, dict)
        assert len(caps) > 0

    def test_inspect_has_summary(self, registry):
        result = registry.inspect()
        summary = result["summary"]
        assert "total" in summary
        assert "available" in summary
        assert summary["total"] > 0

    def test_capability_statuses_valid(self, registry):
        result = registry.inspect()
        caps = result["capabilities"]
        valid_statuses = {"AVAILABLE", "UNAVAILABLE", "NOT_CONFIGURED", "UNKNOWN", "AVAILABLE_WITH_LIMITATIONS"}
        for cap_id, cap_data in caps.items():
            assert cap_data["status"] in valid_statuses, f"Invalid status for {cap_id}: {cap_data['status']}"

    def test_get_capability_returns_spec(self, registry):
        cap = registry.get_capability("transcription")
        assert cap is not None
        assert cap["capability_id"] == "transcription"

    def test_get_capability_unknown(self, registry):
        cap = registry.get_capability("nonexistent")
        assert cap is None

    def test_for_task_returns_relevant(self, registry):
        caps = registry.for_task("transcribe")
        assert "transcription" in caps

    def test_for_task_unknown_returns_empty(self, registry):
        caps = registry.for_task("nonexistent_task")
        assert caps == {}

    def test_quality_in_range(self, registry):
        result = registry.inspect()
        caps = result["capabilities"]
        for cap_id, cap_data in caps.items():
            assert 0.0 <= cap_data["quality"] <= 1.0, f"Quality out of range for {cap_id}"

    def test_cost_class_valid(self, registry):
        result = registry.inspect()
        caps = result["capabilities"]
        valid_costs = {"free", "cheap", "premium", "unknown"}
        for cap_id, cap_data in caps.items():
            assert cap_data["cost_class"] in valid_costs, f"Invalid cost_class for {cap_id}"

    def test_cache_works(self, registry):
        r1 = registry.inspect()
        r2 = registry.inspect()
        assert r1 is r2

    def test_cache_expires(self, registry):
        registry.CACHE_TTL = 0
        r1 = registry.inspect()
        r2 = registry.inspect()
        assert r1 is not r2

    def test_summary_consistent(self, registry):
        result = registry.inspect()
        caps = result["capabilities"]
        summary = result["summary"]
        assert summary["total"] == len(caps)
        assert summary["available"] + summary["unavailable"] + summary["not_configured"] + summary["degraded"] == summary["total"]