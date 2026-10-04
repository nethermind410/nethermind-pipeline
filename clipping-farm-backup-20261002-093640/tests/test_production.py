import tempfile, unittest
from pathlib import Path
from clipping_farm.db import DB
from clipping_farm.pipeline import ClippingPipeline
from clipping_farm.candidates import generate_candidates, rank, Candidate
from clipping_farm.selection import select
from clipping_farm.qc import run_qc, render_qc_text
from clipping_farm.repair import repair_candidate
from clipping_farm.export import assert_publishable, write_review_manifest

class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.f=tempfile.NamedTemporaryFile(suffix=".db"); self.db=DB(self.f.name)
        self.db.set_rights("s","AUTHORISED",{"basis":"fixture"})
    def tearDown(self): self.f.close()
    def test_pipeline_builds_parallel_frontier(self):
        p=ClippingPipeline(self.db).create("s",budget=.50); self.db.promote_ready()
        rows={r["id"]:r for r in self.db.status()}
        for key in ("metadata","analyse_audio","analyse_scenes","transcribe"):
            self.assertEqual(rows[p.jobs[key]]["state"],"READY")
        self.assertEqual(rows[p.jobs["generate_candidates"]]["state"],"PENDING")
    def test_candidates_rank_and_diversify(self):
        cs=generate_candidates([
            {"start":0,"end":12,"text":"Why this works is actually surprising and useful."},
            {"start":10,"end":24,"text":"Here is the result, which is why this matters."},
            {"start":60,"end":75,"text":"Never expect this final example to behave normally."}])
        chosen=select(rank(cs),limit=2); self.assertGreaterEqual(len(chosen),1); self.assertLessEqual(len(chosen),2)
    def test_qc_is_explicit(self):
        q=run_qc(Candidate(0,12,"This is a complete thought.",{"standalone":.8}))
        self.assertTrue(q.passed); self.assertIn("Standalone",render_qc_text(q)); self.assertIn("PASS",render_qc_text(q))
    def test_repair_is_bounded(self):
        c=Candidate(0,4,"Incomplete",{"standalone":.8})
        _,_,attempts=repair_candidate(c,run_qc,max_repairs=2,extend=1); self.assertLessEqual(attempts,2)
    def test_publish_requires_approval(self):
        with self.assertRaises(PermissionError): assert_publishable(self.db,"export")
        self.db.approve("export",True); self.assertTrue(assert_publishable(self.db,"export"))
    def test_review_manifest_does_not_publish(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"review.json"; out=write_review_manifest(p,"s",[{"id":"clip1"}])
            self.assertEqual(out["state"],"READY_FOR_REVIEW"); self.assertTrue(p.exists())
    def test_rights_block_pipeline(self):
        self.db.set_rights("bad","UNKNOWN")
        with self.assertRaises(PermissionError): ClippingPipeline(self.db).create("bad")

if __name__=="__main__": unittest.main()
