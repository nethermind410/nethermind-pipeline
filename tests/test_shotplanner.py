"""
Shot Planner tests. No network, no extra dependencies.

    python3 -m unittest discover -s tests -v
"""
import copy
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from shotplanner import beats as B  # noqa: E402
from shotplanner.compiler import PlanError, compile_plan  # noqa: E402
from shotplanner.text import align_spans, tokens  # noqa: E402
from shotplanner.validate import validate_plan  # noqa: E402


def load(rel):
    with open(os.path.join(ROOT, rel)) as f:
        return json.load(f)


BRIEF = load("briefs/immortal_jellyfish.json")
BEATS = load("beats/immortal_jellyfish.beats.json")


class Example(unittest.TestCase):
    def setUp(self):
        self.plan = compile_plan(BRIEF, BEATS, backend="manual:test")

    def test_valid_and_complete(self):
        errs, _ = validate_plan(self.plan)
        self.assertEqual(errs, [])
        self.assertEqual(len(self.plan["shots"]), 13)
        joined = " ".join(s["narration"]["text"] for s in self.plan["shots"])
        self.assertEqual(joined, self.plan["script"]["text"])

    def test_example_sentence_is_split_into_visual_beats(self):
        # the transformation sentence becomes several shots, not one "jellyfish swimming"
        n03 = [s for s in self.plan["shots"] if "N03" in s["narration"]["sentence_ids"]]
        self.assertGreaterEqual(len(n03), 3)
        facts = {v["id"] for v in self.plan["visual_information"] if v["sentence_id"] == "N03"}
        shown = {v for s in n03 for v in s["visual"]["communicates"]}
        self.assertEqual(facts, shown)

    def test_state_change_gets_first_last_frames(self):
        s05 = self.plan["shots"][4]
        self.assertEqual(s05["generation"]["mode"], "i2v_first_last")
        roles = [k["role"] for k in s05["generation"]["keyframes"]]
        self.assertEqual(roles, ["start", "end"])
        start, end = (k["prompt"] for k in s05["generation"]["keyframes"])
        self.assertIn("torn, notched bell rim", start)
        self.assertIn("shrunk to about half size", end)
        self.assertNotIn("smaller by the end", start)  # the start image isn't asked to show the end

    def test_video_prompt_is_motion_only(self):
        vp = self.plan["shots"][0]["generation"]["video"]["prompt"]
        self.assertTrue(vp.startswith("Camera:"))
        self.assertNotIn("dark-field illumination", vp)  # lighting lives in the keyframe

    def test_negative_prompt_merges_sources_without_no(self):
        neg = self.plan["shots"][0]["generation"]["negative_prompt"]
        for item in ("watermark", "bioluminescent glow", "scuba divers", "more than one jellyfish"):
            self.assertIn(item, neg)
        self.assertNotRegex(neg, r"(^|, )no ")

    def test_continuity_links(self):
        s = self.plan["shots"]
        self.assertIsNone(s[0]["continuity"]["previous_shot"])
        self.assertEqual(s[4]["continuity"]["previous_shot"], "S04")
        self.assertIn("adult_injured", s[4]["continuity"]["previous_shot_state"])
        self.assertIsNone(s[-1]["continuity"]["next_shot"])

    def test_every_must_show_and_must_happen_has_qc(self):
        for s in self.plan["shots"]:
            qtext = " ".join(q["description"] for q in s["qc"]["checks"])
            for m in s["must_show"] + s["must_happen"]:
                self.assertIn(m, qtext)

    def test_timing_is_cumulative_and_clip_is_long_enough(self):
        t = 0.0
        for s in self.plan["shots"]:
            self.assertAlmostEqual(s["timing"]["start_s"], t, places=1)
            self.assertGreaterEqual(s["generation"]["video"]["duration_s"], s["timing"]["estimated_duration_s"])
            t += s["timing"]["estimated_duration_s"]


class Errors(unittest.TestCase):
    def beats(self):
        return copy.deepcopy(BEATS)

    def assertPlanError(self, beats, fragment):
        with self.assertRaises(PlanError) as cm:
            compile_plan(BRIEF, beats)
        self.assertTrue(any(fragment in e for e in cm.exception.errors), cm.exception.errors)

    def test_narration_must_match_script(self):
        b = self.beats()
        b["shots"][1]["narration"] = "It's named Turritopsis dohrnii,"
        self.assertPlanError(b, "does not continue the script")

    def test_narration_must_cover_script(self):
        b = self.beats()
        b["shots"].pop()
        self.assertPlanError(b, "not covered")

    def test_unknown_state(self):
        b = self.beats()
        b["shots"][0]["refs"][0]["start_state"] = "sleeping"
        self.assertPlanError(b, "has no state 'sleeping'")

    def test_visual_information_must_be_shown(self):
        b = self.beats()
        b["shots"][3]["communicates"] = ["V04"]  # drop V05 (the injury)
        self.assertPlanError(b, "V05")

    def test_bad_camera_value(self):
        b = self.beats()
        b["shots"][0]["movement"] = "whip pan"
        self.assertPlanError(b, "movement 'whip_pan'")

    def test_continuous_transition_needs_matching_state(self):
        b = self.beats()
        b["shots"][4]["refs"][0]["start_state"] = "adult_healthy"  # S04 ended adult_injured
        self.assertPlanError(b, "continuous from S04")

    def test_tampered_plan_fails_validation(self):
        plan = compile_plan(BRIEF, BEATS)
        plan["shots"][2]["narration"]["word_start"] += 1
        errs, _ = validate_plan(plan)
        self.assertTrue(any("gap or overlap" in e for e in errs), errs)


class Text(unittest.TestCase):
    def test_alignment_tolerates_case_and_quotes(self):
        toks = tokens("It’s small. Very small.")
        ranges, errs = align_spans(toks, ["it's SMALL.", "Very small"])
        self.assertEqual(errs, [])
        self.assertEqual(ranges, [(0, 2), (2, 4)])


class Heuristic(unittest.TestCase):
    def test_draft_is_valid_but_needs_review(self):
        plan = compile_plan(BRIEF, B.heuristic(BRIEF), backend="heuristic")
        self.assertEqual(validate_plan(plan)[0], [])
        self.assertTrue(all(s["status"] == "NEEDS_REVIEW" for s in plan["shots"]))
        self.assertGreater(len(plan["shots"]), len(plan["script"]["sentences"]))  # clause-level, not per sentence


class FakeProvider:
    label = "fake:test"

    def __init__(self, replies):
        self.replies, self.prompts = list(replies), []

    def generate_json(self, system, prompt):
        self.prompts.append(prompt)
        return self.replies.pop(0)


class LLMLoop(unittest.TestCase):
    def test_errors_are_fed_back_and_fixed(self):
        bad = copy.deepcopy(BEATS)
        bad["shots"][0]["refs"][0]["start_state"] = "sleeping"
        prov = FakeProvider([json.dumps(bad), "```json\n" + json.dumps(BEATS) + "\n```"])
        out = B.from_llm(BRIEF, prov, log=lambda *_: None)
        self.assertEqual(out, BEATS)
        self.assertIn("has no state 'sleeping'", prov.prompts[1])

    def test_gives_up_after_max_repairs(self):
        prov = FakeProvider(["not json"] * 3)
        with self.assertRaises(PlanError):
            B.from_llm(BRIEF, prov, max_repairs=2, log=lambda *_: None)


if __name__ == "__main__":
    unittest.main()
