import os
import unittest

from clipping_farm.adaptive_brain import AdaptiveBrain
from clipping_farm.brain import DeterministicBrain
from clipping_farm.candidates import Candidate
from clipping_farm.db import DB
from clipping_farm.evidence import build_packet
from clipping_farm.model_registry import ModelRegistry, ModelSpec
from clipping_farm.providers import BrainProvider, ProviderResult, DeterministicProvider
from clipping_farm.provider_adapters import ProviderTimeout
from clipping_farm.provider_health import ProviderHealth


class TimeoutProvider(BrainProvider):
    name = "timeout-provider"
    modality = "multimodal"
    def analyse(self, packet):
        raise ProviderTimeout("simulated timeout")


class ProviderLayerTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db")
        self.db = DB(self.tmp.name)

    def tearDown(self):
        self.tmp.close()

    def packet(self, standalone=.2):
        c = Candidate(0, 12, "test", {"standalone": standalone, "hook": .2, "payoff": .2})
        return build_packet(c, [{"start":0,"end":12,"text":"test"}], {"peak":.1}, [], [], {"duration":12})

    def adaptive(self, provider=None):
        a = AdaptiveBrain(self.db, health=ProviderHealth(cooldown_seconds=999))
        a.register_provider(DeterministicProvider(DeterministicBrain()))
        if provider: a.register_provider(provider)
        return a

    def test_capability_mismatch_is_not_selected(self):
        r = ModelRegistry([ModelSpec("text-only","brain.reasoning","text","cheap",.001,.95,.9)])
        self.assertIsNone(r.choose("brain.reasoning", tier="cheap", quality_required=.7, budget=.01, modality="multimodal"))

    def test_unavailable_provider_falls_back_without_crashing(self):
        a = self.adaptive(TimeoutProvider())
        r = ModelRegistry([ModelSpec("timeout-provider","brain.reasoning","multimodal","cheap",.005,.84,.8)])
        a.registry = r
        out = a.analyse(self.packet(.2), job_id="timeout", budget=.01)
        self.assertEqual(out.result.model, "deterministic")
        self.assertTrue(any(x.get("status") == "provider_failed" for x in out.trace))

    def test_health_degrades_after_repeated_failure(self):
        h = ProviderHealth(cooldown_seconds=999)
        h.failure("x","one"); self.assertEqual(h.state("x"), "HEALTHY")
        h.failure("x","two"); self.assertEqual(h.state("x"), "DEGRADED")
        self.assertFalse(h.available("x"))

    def test_zero_budget_never_calls_paid_provider(self):
        class Explode(BrainProvider):
            name="explode"; modality="multimodal"
            def analyse(self,packet): raise AssertionError("paid provider called")
        a=self.adaptive(Explode())
        a.registry=ModelRegistry([ModelSpec("explode","brain.reasoning","multimodal","cheap",.005,.84,.8)])
        out=a.analyse(self.packet(.2), budget=0)
        self.assertTrue(out.blocked)

if __name__ == "__main__":
    unittest.main()
