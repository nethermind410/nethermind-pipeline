import tempfile, unittest
from pathlib import Path
from clipping_farm.db import DB
from clipping_farm.brain import DeterministicBrain
from clipping_farm.candidates import Candidate
from clipping_farm.context import standalone_evidence
from clipping_farm.worker import Worker

class DeterministicTests(unittest.TestCase):
    def setUp(self):
        self.f=tempfile.NamedTemporaryFile(suffix=".db")
        self.db=DB(self.f.name)
    def tearDown(self): self.f.close()

    def test_brain_produces_evidence_and_decision(self):
        c=Candidate(0,20,"Why this surprising result actually matters because the result changes everything.",
                    {"hook":.9,"payoff":.8,"context":.8,"standalone":.8,"information":.8,"novelty":.7})
        ctx=standalone_evidence(c,[{"start":0,"end":20,"text":c.text}])
        d=DeterministicBrain().analyse(c,context=ctx,audio={"peak":.2},scenes=[1,2],frames=[])
        self.assertIn(d.decision,{"accept","reject"})
        self.assertGreaterEqual(d.confidence,.5)
        self.assertTrue(d.evidence)

    def test_worker_claim_respects_capability(self):
        self.db.add_job("audio","analysis_agent",{},idempotency_key="audio")
        self.db.add_job("video","analysis_agent",{},idempotency_key="video")
        w=Worker(self.db,"audio-worker",capabilities=["audio"])
        job=self.db.claim(w.id,capabilities=w.capabilities)
        self.assertEqual(job["task"],"audio")

    def test_retry_returns_ready_without_fake_intermediate_state(self):
        j,_=self.db.add_job("x","a",{},idempotency_key="x",max_attempts=2)
        self.db.promote_ready()
        claimed=self.db.claim("w",capabilities=["x"])
        self.assertIsNotNone(claimed)
        self.assertTrue(self.db.start(claimed["id"],"w"))
        self.db.fail(claimed["id"],"w","temporary",True)
        row=self.db.cx.execute("select state,attempts from jobs where id=?",(claimed["id"],)).fetchone()
        self.assertEqual(row["state"],"READY")
        self.assertEqual(row["attempts"],1)
