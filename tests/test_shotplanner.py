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


class TextEdgeCases(unittest.TestCase):
    """Regression tests from the first stress run (pass 1)."""

    def split(self, text):
        from shotplanner.text import sentences
        t = tokens(text)
        return [" ".join(t[a:b]) for a, b in sentences(t)]

    def test_abbreviations_do_not_end_sentences(self):
        self.assertEqual(self.split("Dr. Smith found it in the U.S. in 1998. It was 3 ft. long."),
                         ["Dr. Smith found it in the U.S. in 1998.", "It was 3 ft. long."])

    def test_lowercase_after_ellipsis_continues_sentence(self):
        self.assertEqual(self.split("Wait... it gets stranger. Much stranger."),
                         ["Wait... it gets stranger.", "Much stranger."])

    def test_closing_quote_ends_sentence(self):
        self.assertEqual(self.split("He said \u201cstop.\u201d Then he left."),
                         ["He said \u201cstop.\u201d", "Then he left."])

    def test_no_sentence_pause_after_abbreviation(self):
        from shotplanner.timing import estimate
        self.assertLess(estimate(tokens("It was 3 ft. long")), estimate(tokens("It was 3 ft. Long")))


class CameraAliases(unittest.TestCase):
    def test_common_terms_are_accepted(self):
        from shotplanner.compiler import _norm
        cases = {("framing", "Close-Up"): "close_up", ("framing", "wide shot"): "wide",
                 ("framing", "ECU"): "extreme_close_up", ("angle", "overhead"): "top_down",
                 ("angle", "low angle"): "low", ("angle", "bird's eye"): "top_down",
                 ("movement", "dolly in"): "slow_push_in", ("movement", "tracking shot"): "track_follow",
                 ("movement", "locked off"): "static", ("transition_in", "hard cut"): "cut",
                 ("motion_intensity", "subtle"): "low"}
        for (k, v), want in cases.items():
            self.assertEqual(_norm(v, k), want, (k, v))

    def test_unknown_term_is_still_an_error(self):
        b = copy.deepcopy(BEATS)
        b["shots"][0]["movement"] = "barrel roll"
        with self.assertRaises(PlanError):
            compile_plan(BRIEF, b)


class ShotLength(unittest.TestCase):
    def test_overlong_shot_is_an_error(self):
        b = copy.deepcopy(BEATS)
        # fold S02..S04 into S01's narration -> one ~12 s shot
        merged = " ".join(s["narration"] for s in b["shots"][:4])
        b["shots"][0]["narration"] = merged
        b["shots"][0]["communicates"] = sorted({v for s in b["shots"][:4] for v in s["communicates"]})
        del b["shots"][1:4]
        with self.assertRaises(PlanError) as cm:
            compile_plan(BRIEF, b)
        self.assertTrue(any("split the shot" in e for e in cm.exception.errors), cm.exception.errors)


class SecondTopic(unittest.TestCase):
    """Regression tests from pass 2: the Greenland shark plan, written in LLM-style wording."""

    def setUp(self):
        self.plan = compile_plan(load("briefs/greenland_shark.json"), load("beats/greenland_shark.beats.json"))

    def test_valid(self):
        self.assertEqual(validate_plan(self.plan)[0], [])

    def test_environment_overrides_film_style(self):
        lab = self.plan["shots"][4]["generation"]["keyframes"][0]["prompt"]
        for leak in ("ROV", "black-blue", "shark skin"):
            self.assertNotIn(leak, lab)
        self.assertIn("microscope lamp", lab)
        self.assertIn("ROV", self.plan["shots"][0]["generation"]["keyframes"][0]["prompt"])

    def test_scale_check_only_with_something_to_compare(self):
        for s in self.plan["shots"]:  # the shark is always alone in frame
            self.assertFalse(any(q["type"] == "scale" for q in s["qc"]["checks"]), s["id"])
        jelly = compile_plan(BRIEF, BEATS)
        with_scale = [s["id"] for s in jelly["shots"] if any(q["type"] == "scale" for q in s["qc"]["checks"])]
        self.assertEqual(with_scale, ["S03", "S13"])  # fingertip, fish

    def test_continuity_check_allows_features_out_of_frame(self):
        eye = self.plan["shots"][11]
        cont = [q["description"] for q in eye["qc"]["checks"] if q["type"] == "continuity"]
        self.assertTrue(any("where visible in frame" in c for c in cont))


class Heuristic(unittest.TestCase):
    def brief(self, script):
        b = copy.deepcopy(BRIEF)
        b["script"] = script
        return b

    def test_short_sentences_are_merged_across_boundaries(self):
        plan = compile_plan(self.brief("Why? Because it can! Really? Yes. It is true."),
                            B.heuristic(self.brief("Why? Because it can! Really? Yes. It is true.")),
                            backend="heuristic")
        self.assertEqual(validate_plan(plan)[0], [])
        self.assertTrue(all(s["timing"]["estimated_duration_s"] >= 1.2 for s in plan["shots"]))

    def test_long_sentence_is_split(self):
        script = " ".join(["word"] * 60) + "."
        plan = compile_plan(self.brief(script), B.heuristic(self.brief(script)), backend="heuristic")
        self.assertGreater(len(plan["shots"]), 4)
        self.assertTrue(all(s["timing"]["estimated_duration_s"] <= 6 for s in plan["shots"]))

    def test_every_repo_script_gets_a_valid_draft(self):
        import glob
        for p in sorted(glob.glob(os.path.join(ROOT, "cfg", "*.json"))):
            cfg = load(os.path.relpath(p, ROOT))
            script = " ".join(s["text"] for s in cfg["segments"] if s.get("text"))
            with self.subTest(cfg=os.path.basename(p)):
                plan = compile_plan(self.brief(script), B.heuristic(self.brief(script)), backend="heuristic")
                self.assertEqual(validate_plan(plan)[0], [])

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
