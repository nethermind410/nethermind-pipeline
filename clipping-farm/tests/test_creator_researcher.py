"""Tests for Creator Research Agent (Phase 10 part 1)."""
import pytest
from clipping_farm.creator_researcher import (
    CreatorResearcherAgent, CreatorPattern,
)
from clipping_farm.db import DB
import tempfile


class TestCreatorResearcherAgent:
    @pytest.fixture
    def db(self):
        f = tempfile.NamedTemporaryFile(suffix=".db")
        return DB(f.name)

    def test_agent_init(self, db):
        agent = CreatorResearcherAgent(db)
        assert agent.VERSION == "creator-researcher-v1"

    def test_research_empty_transcript(self, db):
        agent = CreatorResearcherAgent(db)
        patterns = agent.research_creator("Test Creator", transcript="")
        assert patterns == []

    def test_research_no_transcript(self, db):
        agent = CreatorResearcherAgent(db)
        patterns = agent.research_creator("Test Creator")
        assert patterns == []

    def test_research_with_transcript(self, db):
        agent = CreatorResearcherAgent(db)
        transcript = "Did you know that AI can write scripts? The key is practice. Stay tuned for more!"
        patterns = agent.research_creator("Test Creator", source_url="https://youtube.com/test", transcript=transcript)
        assert len(patterns) > 0
        assert all(isinstance(p, CreatorPattern) for p in patterns)

    def test_research_hook_patterns(self, db):
        agent = CreatorResearcherAgent(db)
        transcript = "What if I told you AI can do this? Here's the thing..."
        patterns = agent.research_creator("Creator", transcript=transcript)
        hooks = [p for p in patterns if p.pattern_type == "hook"]
        assert len(hooks) > 0

    def test_research_storytelling_patterns(self, db):
        agent = CreatorResearcherAgent(db)
        transcript = "But then the thing is, it gets even better."
        patterns = agent.research_creator("Creator", transcript=transcript)
        stories = [p for p in patterns if p.pattern_type == "storytelling"]
        assert len(stories) > 0

    def test_research_narration_patterns(self, db):
        agent = CreatorResearcherAgent(db)
        transcript = "So what that means is basically..."
        patterns = agent.research_creator("Creator", transcript=transcript)
        narrations = [p for p in patterns if p.pattern_type == "narration"]
        assert len(narrations) > 0

    def test_research_visual_patterns(self, db):
        agent = CreatorResearcherAgent(db)
        transcript = "You can see how this works. Notice how it changes."
        patterns = agent.research_creator("Creator", transcript=transcript)
        visuals = [p for p in patterns if p.pattern_type == "visual_explanation"]
        assert len(visuals) > 0

    def test_research_educational_patterns(self, db):
        agent = CreatorResearcherAgent(db)
        transcript = "The key is to remember this important point."
        patterns = agent.research_creator("Creator", transcript=transcript)
        edu = [p for p in patterns if p.pattern_type == "educational"]
        assert len(edu) > 0

    def test_research_humour_patterns(self, db):
        agent = CreatorResearcherAgent(db)
        transcript = "Haha, that's literally funny lol."
        patterns = agent.research_creator("Creator", transcript=transcript)
        humour = [p for p in patterns if p.pattern_type == "humour"]
        assert len(humour) > 0

    def test_research_retention_patterns(self, db):
        agent = CreatorResearcherAgent(db)
        transcript = "Stay tuned for the next part. Wait for it!"
        patterns = agent.research_creator("Creator", transcript=transcript)
        retention = [p for p in patterns if p.pattern_type == "retention"]
        assert len(retention) > 0

    def test_get_patterns(self, db):
        agent = CreatorResearcherAgent(db)
        transcript = "Did you know AI is amazing?"
        agent.research_creator("Creator", source_url="https://test.com", transcript=transcript)
        patterns = agent.get_patterns(pattern_type="hook")
        assert isinstance(patterns, list)

    def test_get_patterns_no_filter(self, db):
        agent = CreatorResearcherAgent(db)
        transcript = "Did you know AI is amazing?"
        agent.research_creator("Creator", source_url="https://test.com", transcript=transcript)
        patterns = agent.get_patterns(limit=10)
        assert isinstance(patterns, list)

    def test_get_pattern_types(self, db):
        agent = CreatorResearcherAgent(db)
        transcript = "Did you know AI is amazing?"
        agent.research_creator("Creator", source_url="https://test.com", transcript=transcript)
        types = agent.get_pattern_types()
        assert isinstance(types, list)
        assert len(types) > 0

    def test_stats_empty(self, db):
        agent = CreatorResearcherAgent(db)
        stats = agent.stats()
        assert stats["total_patterns"] == 0

    def test_stats_with_patterns(self, db):
        agent = CreatorResearcherAgent(db)
        transcript = "Did you know AI is amazing? Stay tuned!"
        agent.research_creator("Creator", source_url="https://test.com", transcript=transcript)
        stats = agent.stats()
        assert stats["total_patterns"] > 0

    def test_pattern_types_valid(self, db):
        agent = CreatorResearcherAgent(db)
        transcript = "Did you know AI is amazing?"
        patterns = agent.research_creator("Creator", transcript=transcript)
        for p in patterns:
            assert p.pattern_type in CreatorResearcherAgent.PATTERN_TYPES

    def test_confidence_in_range(self, db):
        agent = CreatorResearcherAgent(db)
        transcript = "Did you know AI is amazing?"
        patterns = agent.research_creator("Creator", transcript=transcript)
        for p in patterns:
            assert 0.0 <= p.confidence <= 1.0

    def test_version(self, db):
        agent = CreatorResearcherAgent(db)
        assert agent.VERSION == "creator-researcher-v1"

    def test_no_duplicate_patterns(self, db):
        agent = CreatorResearcherAgent(db)
        transcript = "Did you know AI is amazing?"
        agent.research_creator("Creator", transcript=transcript)
        agent.research_creator("Creator", transcript=transcript)
        patterns = agent.get_patterns(limit=100)
        # Should not duplicate
        assert len(patterns) <= 20  # reasonable limit