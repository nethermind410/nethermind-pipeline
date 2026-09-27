import tempfile
import unittest

from clipping_farm.adaptive_brain import AdaptiveBrain
from clipping_farm.brain import DeterministicBrain
from clipping_farm.candidates import Candidate
from clipping_farm.db import DB
from clipping_farm.evidence import build_packet
from clipping_farm.mock_providers import CheapMockProvider, PremiumMockProvider
from clipping_farm.providers import DeterministicProvider


class AdaptiveBrainTests(unittest.TestCase):
    def setUp(self):
        self.f = tempfile.NamedTemporaryFile(suffix=".db")
        self.db = DB(self.f.name)
        self.adaptive = AdaptiveBrain(self.db)
        self.adaptive.register_provider(DeterministicProvider(DeterministicBrain()))
        self.adaptive.register_provider(CheapMockProvider())
        self.adaptive.register_provider(PremiumMockProvider())

    def tearDown(self):
        self.f.close()

    def packet(self, standalone, hook=.2, payoff=.2, context=.3):
        c = Candidate(
            0, 12, "candidate",
            {"hook": hook, "payoff": payoff, "context": context,
             "standalone": standalone, "information": .2, "novelty": .2},
        )
        return build_packet(
            c, [{"start": 0, "end": 12, "text": "candidate"}],
            {"peak": .1}, [], [], {"duration": 12},
        )

    def test_high_confidence_does_not_pay(self):
        packet = self.packet(.9, hook=.9, payoff=.9, context=.9)
        out = self.adaptive.analyse(packet, budget=.10)
        self.assertEqual(out.result.model, "deterministic")
        self.assertFalse(any(x.get("status") == "executed" and x.get("model") == "cheap-mock"
                             for x in out.trace))

    def test_low_confidence_escalates_to_cheap_only(self):
        packet = self.packet(.8, hook=.2, payoff=.2, context=.2)
        out = self.adaptive.analyse(packet, job_id="cheap-job", budget=.01)
        self.assertEqual(out.result.model, "cheap-mock")
        self.assertFalse(out.blocked)

    def test_low_confidence_can_reach_premium(self):
        packet = self.packet(.4, hook=.2, payoff=.2, context=.2)
        out = self.adaptive.analyse(packet, job_id="premium-job", budget=.10)
        self.assertEqual(out.result.model, "premium-mock")
        self.assertTrue(any(x.get("model") == "cheap-mock" for x in out.trace))
        self.assertTrue(any(x.get("model") == "premium-mock" for x in out.trace))

    def test_zero_budget_blocks_paid_escalation(self):
        packet = self.packet(.4, hook=.2, payoff=.2, context=.2)
        out = self.adaptive.analyse(packet, budget=0)
        self.assertTrue(out.blocked)
        self.assertEqual(out.result.model, "deterministic")

    def test_provider_cache_avoids_second_call(self):
        packet = self.packet(.8, hook=.2, payoff=.2, context=.2)
        first = self.adaptive.analyse(packet, job_id="cache-1", budget=.01)
        second = self.adaptive.analyse(packet, job_id="cache-2", budget=.01)
        self.assertEqual(first.result.model, "cheap-mock")
        self.assertEqual(second.result.model, "cheap-mock")
        self.assertTrue(any(x.get("status") == "cache_hit" for x in second.trace))


if __name__ == "__main__":
    unittest.main()
