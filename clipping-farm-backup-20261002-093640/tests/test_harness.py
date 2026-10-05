import tempfile, unittest
from clipping_farm.db import DB
from clipping_farm.worker import Worker
from clipping_farm.harness import ModelRouter, RightsGate

class HarnessTests(unittest.TestCase):
 def setUp(self): self.f=tempfile.NamedTemporaryFile(suffix=".db"); self.db=DB(self.f.name)
 def tearDown(self): self.f.close()
 def test_idempotency(self):
  a,_=self.db.add_job("x","a",{},idempotency_key="same"); b,dup=self.db.add_job("x","a",{},idempotency_key="same"); self.assertTrue(dup); self.assertEqual(a["id"],b["id"])
 def test_rights_hard_gate(self):
  with self.assertRaises(PermissionError): RightsGate(self.db).check("nope")
  self.db.set_rights("s","AUTHORISED"); RightsGate(self.db).check("s")
 def test_dependency_parallel_readiness(self):
  a,_=self.db.add_job("a","a",{},idempotency_key="a"); b,_=self.db.add_job("b","b",{},idempotency_key="b",depends_on=[a["id"]]); c,_=self.db.add_job("c","c",{},idempotency_key="c")
  self.db.promote_ready(); states={r["id"]:r["state"] for r in self.db.status()}; self.assertEqual(states[a["id"]],"READY"); self.assertEqual(states[c["id"]],"READY"); self.assertEqual(states[b["id"]],"PENDING")
 def test_atomic_claim(self):
  self.db.add_job("x","a",{},idempotency_key="x"); self.db.promote_ready(); w1=Worker(self.db,"w1"); w2=Worker(self.db,"w2"); j=w1.db.claim("w1"); self.assertIsNotNone(j); self.assertIsNone(w2.db.claim("w2"))
 def test_router_free_first(self):
  r=ModelRouter(self.db).route("silence_detection",.99,10,"h","audio"); self.assertEqual(r["method"],"deterministic")
  r=ModelRouter(self.db).route("classify",.5,.01,"h"); self.assertEqual(r["method"],"cheap")

if __name__=="__main__":unittest.main()
