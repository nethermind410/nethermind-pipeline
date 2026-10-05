import tempfile, unittest
from clipping_farm.db import DB
from clipping_farm.brain import DeterministicBrain
from clipping_farm.candidates import Candidate
from clipping_farm.evidence import build_packet
from clipping_farm.harness import ModelRouter

class BrainTests(unittest.TestCase):
 def setUp(self):
  self.f=tempfile.NamedTemporaryFile(suffix=".db"); self.db=DB(self.f.name)
 def tearDown(self): self.f.close()
 def test_packet_is_stable_and_compact(self):
  c=Candidate(10,30,"Why this matters because the result is surprising.",{"standalone":.8})
  p=build_packet(c,[{"start":0,"end":10,"text":"Earlier context."},{"start":30,"end":40,"text":"Following context."}],{"peak":.2},[{"start":10,"end":20}], [{"time":12,"path":"f.jpg","sha256":"x"}],{"format":{"duration":"40"}})
  self.assertTrue(p.digest()); self.assertIn("Earlier",p.context_before); self.assertIn("Following",p.context_after)
 def test_router_blocks_paid_without_budget(self):
  r=ModelRouter(self.db).route("multimodal_reasoning",.95,0,"abc","multimodal")
  self.assertEqual(r["method"],"blocked")
 def test_deterministic_brain_marks_low_confidence_for_escalation(self):
  c=Candidate(0,12,"Short.",{"hook":.2,"payoff":.2,"context":.4,"standalone":.4,"information":.2,"novelty":.2})
  d=DeterministicBrain().analyse(c,audio={"peak":.01},scenes=[],frames=[])
  self.assertTrue(d.escalate)

if __name__=="__main__": unittest.main()
