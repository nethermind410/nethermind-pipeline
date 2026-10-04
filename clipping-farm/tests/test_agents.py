"""Tests for the agent-based content system."""
import tempfile
import unittest

from clipping_farm.agents.trending import TrendingAgent, TrendingItem
from clipping_farm.agents.script_writer import ScriptWriterAgent, Script
from clipping_farm.agents.content_referencer import ContentReferencerAgent, ReferencePack
from clipping_farm.agents.approval_gate import ApprovalGate, ApprovalRequest
from clipping_farm.agents.agent_registry import AgentRegistry, AgentInfo
from clipping_farm.agents.orchestrator import Orchestrator, PipelineState
from clipping_farm.db import DB


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.f = tempfile.NamedTemporaryFile(suffix=".db")
        self.db = DB(self.f.name)


class TrendingAgentTests(AgentTests):
    def test_discover_writes_jev(self):
        agent = TrendingAgent(self.db, min_hot_score=0.0)
        self.db.cx.execute(
            "INSERT INTO sources(source_id, location, kind, sha256, size_bytes, metadata, provenance, first_seen_at, last_seen_at)"
            "VALUES(?,?,?,?,?,?,?,?,?)",
            ("test-source", "/tmp/test.mp4", "file", "abc123", 1000,
             '{"title": "Marvel Comic Review"}', '{"ingestion":"local_file"}', 1000000, 1000000),
        )
        self.db.cx.commit()
        items = agent.discover()
        self.assertGreater(len(items), 0)
        self.assertIsInstance(items[0], TrendingItem)
        self.assertGreater(items[0].hot_score, 0)

    def test_jev_persists(self):
        agent = TrendingAgent(self.db, min_hot_score=0.0)
        self.db.cx.execute(
            "INSERT INTO sources(source_id, location, kind, sha256, size_bytes, metadata, provenance, first_seen_at, last_seen_at)"
            "VALUES(?,?,?,?,?,?,?,?,?)",
            ("test-source2", "/tmp/test2.mp4", "file", "def456", 2000,
             '{"title": "DC Comic"}', '{"ingestion":"local_file"}', 1000000, 1000000),
        )
        self.db.cx.commit()
        items = agent.discover()
        if items:
            jev = agent.get_jev(items[0].jev_id)
            self.assertIsNotNone(jev)
            self.assertEqual(jev["agent"], "trending")

    def test_list_jevs(self):
        agent = TrendingAgent(self.db, min_hot_score=0.0)
        self.db.cx.execute(
            "INSERT INTO sources(source_id, location, kind, sha256, size_bytes, metadata, provenance, first_seen_at, last_seen_at)"
            "VALUES(?,?,?,?,?,?,?,?,?)",
            ("test-source3", "/tmp/test3.mp4", "file", "ghi789", 3000,
             '{"title": "Anime Review"}', '{"ingestion":"local_file"}', 1000000, 1000000),
        )
        self.db.cx.commit()
        agent.discover()
        jevs = agent.list_jevs(limit=10)
        self.assertGreater(len(jevs), 0)


class ScriptWriterAgentTests(AgentTests):
    def test_write_script(self):
        agent = ScriptWriterAgent(self.db)
        jev_id = "jev:test123"
        self.db.put_artifact(jev_id, "trending_jev", "test-source", jev_id, {
            "jev_id": jev_id,
            "agent": "trending",
            "source_id": "test-source",
            "title": "Test Comic",
            "hot_score": 7.5,
            "decision": "trending",
        })
        script = agent.write_script(jev_id, source_material={"transcript": [
            {"start": 0, "end": 3, "text": "Welcome to the show."},
            {"start": 3, "end": 10, "text": "Today we discuss comics."},
            {"start": 10, "end": 13, "text": "Thanks for watching."},
        ]})
        self.assertIsInstance(script, Script)
        self.assertEqual(script.title, "Test Comic")
        self.assertEqual(len(script.steps), 3)

    def test_script_jev_written(self):
        agent = ScriptWriterAgent(self.db)
        jev_id = "jev:test456"
        self.db.put_artifact(jev_id, "trending_jev", "test-source", jev_id, {
            "jev": {
                "jev_id": jev_id,
                "agent": "trending",
                "source_id": "test-source",
                "title": "Test Script",
                "hot_score": 6.0,
            }
        })
        script = agent.write_script(jev_id)
        # Read directly from DB
        rows = self.db.cx.execute('SELECT metadata FROM artifacts WHERE kind="script_jev"').fetchall()
        self.assertGreater(len(rows), 0)
        meta = __import__("json").loads(rows[0]["metadata"])
        self.assertIn("jev", meta)
        self.assertEqual(meta["jev"]["agent"], "script_writer")


class ContentReferencerTests(AgentTests):
    def test_build_pack(self):
        agent = ContentReferencerAgent(self.db)
        jev_id = "jev:test789"
        self.db.put_artifact(jev_id, "script_jev", "test-source", jev_id, {
            "jev_id": jev_id,
            "agent": "script_writer",
            "script_id": "script:abc",
            "source_id": "test-source",
            "title": "Test Pack",
        })
        pack = agent.build_pack(jev_id)
        self.assertIsInstance(pack, ReferencePack)
        self.assertIsNotNone(pack.pack_id)

    def test_pack_jev_written(self):
        agent = ContentReferencerAgent(self.db)
        jev_id = "jev:test101"
        self.db.put_artifact(jev_id, "script_jev", "test-source", jev_id, {
            "jev_id": jev_id,
            "agent": "script_writer",
            "script_id": "script:def",
            "source_id": "test-source",
        })
        pack = agent.build_pack(jev_id)
        rows = self.db.cx.execute('SELECT metadata FROM artifacts WHERE kind="pack_jev"').fetchall()
        self.assertGreater(len(rows), 0)
        meta = __import__("json").loads(rows[0]["metadata"])
        self.assertIn("jev", meta)
        self.assertEqual(meta["jev"]["agent"], "content_referencer")


class ApprovalGateTests(AgentTests):
    def test_request_approval(self):
        gate = ApprovalGate(self.db)
        approval = gate.request_approval(
            jev_id="jev:test1",
            agent="trending",
            title="Test Approval",
        )
        self.assertIsInstance(approval, ApprovalRequest)
        self.assertEqual(approval.state, "PENDING")

    def test_review(self):
        gate = ApprovalGate(self.db)
        approval = gate.request_approval(
            jev_id="jev:test2",
            agent="trending",
            title="Test Review",
        )
        reviewed = gate.review(approval.approval_id, "APPROVED", "Looks good")
        self.assertEqual(reviewed.state, "APPROVED")
        self.assertEqual(reviewed.review_notes, "Looks good")

    def test_get_pending(self):
        gate = ApprovalGate(self.db)
        gate.request_approval(jev_id="jev:test3", agent="trending", title="Pending")
        pending = gate.get_pending()
        self.assertGreater(len(pending), 0)

    def test_stats(self):
        gate = ApprovalGate(self.db)
        gate.request_approval(jev_id="jev:test4", agent="trending", title="Stat Test")
        stats = gate.stats()
        self.assertIn("PENDING", stats)


class AgentRegistryTests(AgentTests):
    def test_register(self):
        registry = AgentRegistry(self.db)
        agent = registry.register("trending")
        self.assertIsInstance(agent, AgentInfo)
        self.assertEqual(agent.name, "Trending Agent")

    def test_heartbeat(self):
        registry = AgentRegistry(self.db)
        registry.register("trending")
        registry.heartbeat("trending", status="ACTIVE", health="HEALTHY")
        agent = registry.get("trending")
        self.assertEqual(agent.status, "ACTIVE")

    def test_available(self):
        registry = AgentRegistry(self.db)
        registry.register("trending")
        registry.register("script_writer")
        available = registry.available()
        self.assertGreater(len(available), 0)

    def test_fail(self):
        registry = AgentRegistry(self.db)
        registry.register("trending")
        registry.fail("trending", "test failure")
        agent = registry.get("trending")
        self.assertEqual(agent.status, "ERROR")
        self.assertEqual(agent.health, "FAILED")

    def test_offline(self):
        registry = AgentRegistry(self.db)
        registry.register("trending")
        registry.offline("trending")
        agent = registry.get("trending")
        self.assertEqual(agent.status, "OFFLINE")


class OrchestratorTests(AgentTests):
    def test_run_pipeline(self):
        orch = Orchestrator(self.db)
        state = orch.run_pipeline("test-source", title="Test Pipeline")
        self.assertIsInstance(state, PipelineState)
        self.assertIsNotNone(state.pipeline_id)

    def test_get_pipeline(self):
        orch = Orchestrator(self.db)
        state = orch.run_pipeline("test-source2", title="Test Get")
        retrieved = orch.get_pipeline(state.pipeline_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.pipeline_id, state.pipeline_id)

    def test_list_pipelines(self):
        orch = Orchestrator(self.db)
        orch.run_pipeline("test-source3", title="Test List")
        pipelines = orch.list_pipelines(limit=10)
        self.assertGreater(len(pipelines), 0)

    def test_stats(self):
        orch = Orchestrator(self.db)
        orch.run_pipeline("test-source4", title="Test Stats")
        stats = orch.stats()
        self.assertIn("pipelines", stats)
        self.assertIn("agents", stats)


if __name__ == "__main__":
    unittest.main()