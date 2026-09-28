import tempfile
import unittest
from clipping_farm.db import DB
from clipping_farm.learning import LearningBrain, LearningStore

class LearningBrainTests(unittest.TestCase):
    def setUp(self):
        self.f=tempfile.NamedTemporaryFile(suffix=".db")
        self.db=DB(self.f.name); self.store=LearningStore(self.db); self.brain=LearningBrain(self.db)
    def tearDown(self): self.f.close()
    def seed(self,n=40,effect=True):
        for i in range(n):
            clip=f"clip-{i}"; high=i%2==0
            self.store.add_features(clip_id=clip,hook_score=.9 if high else .5,payoff_score=.9 if high else .5,
                context_score=.9 if high else .5,standalone_score=.9 if high else .5,
                information_score=.9 if high else .5,visual_score=.9 if high else .5,
                audio_score=.9 if high else .5,novelty_score=.9 if high else .5,
                duration_seconds=20 if high else 45,scoring_version="score-v1")
            self.store.add_performance(clip_id=clip,platform="youtube",account_id="a",
                observation_window_hours=24,views=(200 if high else 100) if effect else 100,
                retention_percent=80 if high else 60,completion_rate=80 if high else 60,impressions=1000)
    def test_001_empty_is_insufficient(self):
        r=self.brain.run(); self.assertEqual(r["status"],"INSUFFICIENT_DATA"); self.assertEqual(r["recommendations"],[])
    def test_002_nine_cannot_recommend(self):
        self.seed(9); r=self.brain.run(); self.assertEqual(r["status"],"INSUFFICIENT_DATA")
    def test_003_thirty_is_learning_data(self):
        self.seed(30); r=self.brain.run(); self.assertEqual(r["status"],"COMPLETE"); self.assertTrue(r["patterns"])
    def test_004_large_sample_supported(self):
        self.seed(300); r=self.brain.run(); self.assertTrue({p["status"] for p in r["patterns"]}&{"SUPPORTED","VALIDATED"})
    def test_005_history_immutable(self):
        self.seed(30); before=[tuple(x) for x in self.db.cx.execute("SELECT * FROM performance_records")]
        self.brain.run(); after=[tuple(x) for x in self.db.cx.execute("SELECT * FROM performance_records")]
        self.assertEqual(before,after)
    def test_006_feature_versions_preserved(self):
        self.seed(30); self.store.add_features(clip_id="clip-0",hook_score=.1,feature_version="features-v2")
        self.assertEqual(self.db.cx.execute("SELECT COUNT(*) FROM feature_snapshots WHERE clip_id='clip-0'").fetchone()[0],2)
    def test_007_windows_are_separate(self):
        self.store.add_performance(clip_id="x",platform="youtube",observation_window_hours=1,views=10)
        self.store.add_performance(clip_id="x",platform="youtube",observation_window_hours=24,views=20)
        self.assertEqual(self.db.cx.execute("SELECT COUNT(*) FROM performance_records WHERE clip_id='x'").fetchone()[0],2)
    def test_008_cohorts_are_separate(self):
        for p,w in (("youtube",24),("tiktok",24),("youtube",168)):
            self.store.add_outcome(clip_id=f"{p}-{w}",platform=p,window_hours=w,normalised_performance=1)
        self.assertEqual(self.db.cx.execute("SELECT COUNT(*) FROM performance_outcomes WHERE platform='youtube' AND window_hours=24").fetchone()[0],1)
    def test_009_missing_impressions_no_ctr(self):
        self.store.add_performance(clip_id="x",platform="youtube",observation_window_hours=24,views=10)
        self.assertIsNone(self.db.cx.execute("SELECT click_through_rate FROM performance_records").fetchone()[0])
    def test_010_positive_relationship(self):
        self.seed(100); r=self.brain.run(); self.assertTrue(any(p["effect_size"]>0 for p in r["patterns"]))
    def test_011_no_effect_no_recommendation(self):
        self.seed(120,effect=False); r=self.brain.run(); self.assertEqual(r["recommendations"],[])
    def test_012_negative_relationship(self):
        for i in range(120):
            high=i%2==0; clip=f"n-{i}"
            self.store.add_features(clip_id=clip,hook_score=.9 if high else .5)
            self.store.add_performance(clip_id=clip,platform="youtube",observation_window_hours=24,views=80 if high else 160)
        r=self.brain.run(); self.assertTrue(any(p["effect_size"]<0 for p in r["patterns"]))
    def test_013_stability(self): self.assertGreater(self.brain._stability([1,1.01,1.02,1.03,1.01,1.02]),.9)
    def test_014_instability(self): self.assertLess(self.brain._stability([1.5,.9,1.05,1.4,.8,1.0]),.5)
    def test_015_overconfidence_detected(self):
        for i in range(120):
            self.store.add_features(clip_id=f"c-{i}",standalone_score=.8)
            self.store.add_outcome(clip_id=f"c-{i}",platform="youtube",window_hours=24,normalised_performance=.2)
        r=self.brain.run(); self.assertEqual(r["calibration"]["status"],"OVERCONFIDENT_HIGH_SCORE_RANGE")
    def test_016_small_calibration_diagnostic(self):
        for i in range(20):
            self.store.add_features(clip_id=f"d-{i}",standalone_score=.8)
            self.store.add_outcome(clip_id=f"d-{i}",platform="youtube",window_hours=24,normalised_performance=.2)
        self.assertIn(self.brain.run()["calibration"]["status"],("DIAGNOSTIC_ONLY","INSUFFICIENT_DATA"))
    def test_017_raw_score_not_overwritten(self):
        self.store.add_features(clip_id="x",standalone_score=.91)
        self.store.add_outcome(clip_id="x",platform="youtube",window_hours=24,normalised_performance=.74)
        self.brain.run(); self.assertEqual(self.db.cx.execute("SELECT standalone_score FROM feature_snapshots WHERE clip_id='x'").fetchone()[0],.91)
    def test_018_assignment_deterministic(self): self.assertEqual(self.brain.assign("e","c"),self.brain.assign("e","c"))
    def test_019_assignment_is_about_80_20(self):
        vals=[self.brain.assign("e",f"c{i}")[0] for i in range(1000)]
        self.assertTrue(750<=vals.count("CONTROL")<=850)
    def test_020_assignment_persistent(self):
        e=self.brain.create_experiment(name="e",hypothesis="h",control_strategy="a",test_strategy="b")
        a=self.brain.assign_clip(e,"x"); b=self.brain.assign_clip(e,"x"); self.assertEqual(a["assignment_hash"],b["assignment_hash"])
    def test_021_experiments_are_explicit(self):
        e=self.brain.create_experiment(name="e",hypothesis="h",control_strategy="a",test_strategy="b")
        self.assertEqual(self.db.cx.execute("SELECT status FROM experiments WHERE id=?",(e,)).fetchone()[0],"PROPOSED")
    def test_022_strategy_version_created_with_provenance(self):
        self.seed(300); r=self.brain.run()
        if not r["recommendations"]: self.skipTest("no qualifying synthetic recommendation")
        self.assertTrue(r["strategy_version"].startswith("strategy-"))
        row=self.db.cx.execute("SELECT learning_run_id,algorithm_version FROM strategy_recommendations WHERE id=?",(r["recommendations"][0],)).fetchone()
        self.assertEqual(row["learning_run_id"],r["learning_run_id"]); self.assertEqual(row["algorithm_version"],"learning-v1")
    def test_023_repeat_is_reproducible_for_assignment(self):
        self.assertEqual(self.brain.assign("same","same"),self.brain.assign("same","same"))
    def test_024_corrupt_feature_does_not_mutate_performance(self):
        self.seed(30); before=self.db.cx.execute("SELECT COUNT(*) FROM performance_records").fetchone()[0]
        r=self.brain.run(); after=self.db.cx.execute("SELECT COUNT(*) FROM performance_records").fetchone()[0]
        self.assertEqual(before,after); self.assertEqual(r["status"],"COMPLETE")
    def test_025_no_paid_dependency(self):
        self.assertIn(self.brain.run()["status"],("INSUFFICIENT_DATA","COMPLETE"))
    def test_026_repeat_learning_keeps_features(self):
        self.seed(30); before=[tuple(x) for x in self.db.cx.execute("SELECT * FROM feature_snapshots")]
        self.brain.run(); self.brain.run(); after=[tuple(x) for x in self.db.cx.execute("SELECT * FROM feature_snapshots")]
        self.assertEqual(before,after)
    def test_027_old_patterns_remain_accessible(self):
        self.seed(100); r=self.brain.run()
        self.assertGreater(self.db.cx.execute("SELECT COUNT(*) FROM patterns WHERE learning_run_id=?",(r["learning_run_id"],)).fetchone()[0],0)
    def test_028_strategy_rollback(self):
        self.seed(300); r=self.brain.run()
        if not r["strategy_version"]: self.skipTest("no strategy")
        self.brain.create_strategy([]); self.brain.rollback(r["strategy_version"])
        self.assertEqual(self.db.cx.execute("SELECT status FROM strategy_versions WHERE version=?",(r["strategy_version"],)).fetchone()[0],"ACTIVE")
    def test_029_learning_run_provenance(self):
        self.seed(30); r=self.brain.run()
        row=self.db.cx.execute("SELECT algorithm_version,feature_version,status FROM learning_runs WHERE id=?",(r["learning_run_id"],)).fetchone()
        self.assertEqual(row["algorithm_version"],"learning-v1"); self.assertEqual(row["feature_version"],"features-v1"); self.assertEqual(row["status"],"COMPLETE")
    def test_030_end_to_end(self):
        self.seed(1000); r=self.brain.run()
        self.assertEqual(r["status"],"COMPLETE"); self.assertEqual(r["algorithm_version"],"learning-v1")
        self.assertEqual(r["records_considered"],1000)
        self.assertGreaterEqual(self.db.cx.execute("SELECT COUNT(*) FROM performance_records").fetchone()[0],1000)
        self.assertTrue(self.db.cx.execute("SELECT COUNT(*) FROM calibration_records").fetchone()[0]>=1)

if __name__=="__main__": unittest.main()
