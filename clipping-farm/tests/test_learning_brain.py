"""Tests for Learning Brain (Phase 9)."""
import pytest
from clipping_farm.learning_brain import LearningBrain, LearningEvent
from clipping_farm.db import DB
import tempfile


class TestLearningBrain:
    @pytest.fixture
    def db(self):
        f = tempfile.NamedTemporaryFile(suffix=".db")
        return DB(f.name)

    def test_brain_init(self, db):
        brain = LearningBrain(db)
        assert brain.VERSION == "learning-brain-v1"

    def test_record_event(self, db):
        brain = LearningBrain(db)
        event_id = brain.record("candidate_accepted", "trending",
                                data={"score": 0.9})
        assert event_id.startswith("learn:")

    def test_record_invalid_type(self, db):
        brain = LearningBrain(db)
        with pytest.raises(ValueError):
            brain.record("invalid_type", "trending")

    def test_get_events(self, db):
        brain = LearningBrain(db)
        brain.record("candidate_accepted", "trending", data={"score": 0.9})
        brain.record("candidate_rejected", "trending", data={"score": 0.3})
        events = brain.get_events(event_type="candidate_accepted")
        assert len(events) == 1
        assert events[0].event_type == "candidate_accepted"

    def test_get_events_no_filter(self, db):
        brain = LearningBrain(db)
        brain.record("candidate_accepted", "trending", data={"score": 0.9})
        brain.record("qc_pass", "trending")
        events = brain.get_events(limit=10)
        assert len(events) == 2

    def test_summarize(self, db):
        brain = LearningBrain(db)
        brain.record("candidate_accepted", "trending", data={"score": 0.9})
        brain.record("candidate_accepted", "trending", data={"score": 0.8})
        brain.record("qc_pass", "trending")
        summary = brain.summarize()
        assert len(summary) >= 2

    def test_summarize_filtered(self, db):
        brain = LearningBrain(db)
        brain.record("candidate_accepted", "trending", data={"score": 0.9})
        brain.record("qc_pass", "trending")
        summary = brain.summarize(event_type="candidate_accepted")
        assert len(summary) == 1
        assert summary[0]["event_type"] == "candidate_accepted"

    def test_recommend_threshold_no_data(self, db):
        brain = LearningBrain(db)
        result = brain.recommend_threshold("trending")
        assert result["confidence"] == 0.0
        assert "no historical data" in result["reason"]

    def test_recommend_threshold_high_pass(self, db):
        brain = LearningBrain(db)
        for i in range(10):
            brain.record("qc_pass", "trending", data={"score": 0.9})
        result = brain.recommend_threshold("trending")
        assert result["recommendation"] <= 0.7
        assert result["confidence"] > 0.8

    def test_recommend_threshold_low_pass(self, db):
        brain = LearningBrain(db)
        for i in range(10):
            brain.record("qc_fail", "trending")
        result = brain.recommend_threshold("trending")
        assert result["recommendation"] >= 0.7
        assert result["confidence"] < 0.5

    def test_recommend_threshold_moderate(self, db):
        brain = LearningBrain(db)
        for i in range(5):
            brain.record("qc_pass", "trending")
        for i in range(5):
            brain.record("qc_fail", "trending")
        result = brain.recommend_threshold("trending")
        assert result["recommendation"] == 0.7

    def test_recommend_provider_no_data(self, db):
        brain = LearningBrain(db)
        result = brain.recommend_provider("trending")
        assert "no provider performance data" in result["reason"]

    def test_recommend_provider(self, db):
        brain = LearningBrain(db)
        brain.record("provider_performance", "trending",
                      data={"provider": "openai", "quality": 0.95, "cost": 0.01})
        brain.record("provider_performance", "trending",
                      data={"provider": "ollama", "quality": 0.85, "cost": 0.0})
        result = brain.recommend_provider("trending")
        assert "recommended_provider" in result

    def test_recommend_workflow_no_events(self, db):
        brain = LearningBrain(db)
        result = brain.recommend_workflow()
        assert "no events" in result["reason"]

    def test_recommend_workflow(self, db):
        brain = LearningBrain(db)
        for i in range(15):
            brain.record("qc_fail", "trending")
        result = brain.recommend_workflow()
        assert len(result["recommendations"]) > 0

    def test_learn_from_pipeline(self, db):
        brain = LearningBrain(db)
        pipeline_state = {"pipeline_id": "pipe:test", "status": "COMPLETE"}
        events = brain.learn_from_pipeline(pipeline_state)
        assert len(events) == 1

    def test_get_stats(self, db):
        brain = LearningBrain(db)
        brain.record("candidate_accepted", "trending")
        brain.record("qc_pass", "trending")
        stats = brain.get_stats()
        assert "candidate_accepted" in stats
        assert "qc_pass" in stats

    def test_version(self, db):
        brain = LearningBrain(db)
        assert brain.VERSION == "learning-brain-v1"

    def test_record_evidence(self, db):
        brain = LearningBrain(db)
        event_id = brain.record(
            "candidate_accepted", "trending",
            evidence={"reason": "high_quality"},
        )
        event = brain.get_events(limit=1)[0]
        assert event.evidence["reason"] == "high_quality"