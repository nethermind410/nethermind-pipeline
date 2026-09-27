import tempfile
import unittest
from pathlib import Path

from clipping_farm.db import DB
from clipping_farm.vision import VisionBrain
from clipping_farm.multimodal import MultimodalCandidateBrain


class VisionMultimodalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db")
        self.db = DB(self.tmp.name)
        self.root = Path(tempfile.mkdtemp())
        self.frames = []
        for i, t in enumerate((1, 3, 5, 7, 9, 11, 13, 15)):
            p = self.root / f"{i}.jpg"
            p.write_bytes(f"frame-{i}".encode())
            self.frames.append({
                "index": i, "time": t, "path": str(p),
                "sha256": f"sha-{i}",
            })

    def tearDown(self):
        self.tmp.close()

    def test_frame_budget_and_temporal_coverage(self):
        brain = VisionBrain(self.db, max_frames=4)
        selected = brain.select_frames(self.frames, 0, 16)
        self.assertEqual(len(selected), 4)
        self.assertEqual(selected[0]["time"], 1)
        self.assertEqual(selected[-1]["time"], 15)

    def test_duplicate_frames_are_removed(self):
        duplicate = dict(self.frames[0])
        duplicate["index"] = 99
        selected = VisionBrain(max_frames=10).select_frames(
            self.frames + [duplicate], 0, 16
        )
        self.assertEqual(len(selected), len(self.frames))

    def test_invalid_frame_is_ignored(self):
        bad = {"time": 2, "path": "/does/not/exist", "sha256": "bad"}
        selected = VisionBrain(max_frames=10).select_frames(
            self.frames + [bad], 0, 16
        )
        self.assertEqual(len(selected), len(self.frames))

    def test_vision_cache_reuses_result(self):
        brain = VisionBrain(self.db, max_frames=4)
        candidate = {"start": 0, "end": 16}
        first = brain.analyse(self.frames, candidate)
        second = brain.analyse(self.frames, candidate)
        self.assertEqual(first.digest(), second.digest())
        self.assertIsNotNone(self.db.get_artifact(
            brain._cache_key(brain.select_frames(self.frames, 0, 16), candidate)
        ))

    def test_no_frames_is_not_positive_evidence(self):
        result = VisionBrain().analyse([], {"start": 0, "end": 10})
        self.assertEqual(result.confidence, 0.0)
        self.assertIn("no_valid_frames", result.evidence)

    def test_missing_visual_evidence_reduces_fusion_confidence(self):
        c = {"scores": {
            "hook": .9, "payoff": .9, "context": .9,
            "standalone": .9, "information": .9, "novelty": .9,
        }}
        brain = MultimodalCandidateBrain()
        no_visual = brain.analyse(c, audio={"peak": .1})
        with_visual = brain.analyse(
            c, audio={"peak": .1},
            visual={"relevance": .9, "evidence": ["visual action confirmed"]},
        )
        self.assertGreater(with_visual.confidence, no_visual.confidence)
        self.assertIn("visual", no_visual.missing_modalities)

    def test_fusion_does_not_invent_missing_audio(self):
        c = {"scores": {
            "hook": .9, "payoff": .9, "context": .9,
            "standalone": .9, "information": .9, "novelty": .9,
        }}
        result = MultimodalCandidateBrain().analyse(c, visual={
            "relevance": .9, "evidence": []
        })
        self.assertIn("audio", result.missing_modalities)

    def test_low_standalone_never_auto_accepts(self):
        c = {"scores": {
            "hook": .99, "payoff": .99, "context": .99,
            "standalone": .40, "information": .99, "novelty": .99,
        }}
        result = MultimodalCandidateBrain().analyse(
            c, audio={"peak": .1},
            visual={"relevance": .99, "evidence": ["visual evidence"]},
        )
        self.assertNotEqual(result.decision, "accept")


if __name__ == "__main__":
    unittest.main()
