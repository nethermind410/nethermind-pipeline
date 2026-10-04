"""Deterministic Reference DNA extraction from persisted Clipping Farm results."""

from __future__ import annotations
import json
from pathlib import Path
from collections import Counter

def _words(text):
    return [w for w in (text or "").replace("\n"," ").split() if w]

def build_reference_dna(db, asset_id):
    asset=db.get_asset(asset_id)
    if not asset: raise KeyError(asset_id)
    source_id=asset.get("source_id") or asset_id
    rows=db.cx.execute(
        "SELECT task,result,state,created_at FROM jobs WHERE json_extract(payload,'$.asset_id')=? OR json_extract(payload,'$.source_id')=? ORDER BY created_at",
        (asset_id,source_id),
    ).fetchall()
    results={}
    for row in rows:
        if row["state"]=="COMPLETE" and row["result"]:
            try: results[row["task"]]=json.loads(row["result"])
            except json.JSONDecodeError: pass

    metadata=results.get("metadata",{}).get("metadata",{})
    transcript=results.get("transcribe",{}).get("transcript",[])
    scenes=results.get("analyse_scenes",{}).get("scenes",[])
    candidates=results.get("score_candidates",{}).get("candidates",[]) or results.get("generate_candidates",{}).get("candidates",[])
    duration=float(metadata.get("format",{}).get("duration") or asset.get("duration") or 0)

    opening=transcript[0] if transcript else None
    opening_text=(opening or {}).get("text","")
    words=_words(opening_text)
    candidate_hooks=sorted(
        [{"start":c.get("start"),"end":c.get("end"),"text":c.get("text",""),"score":c.get("scores",{}).get("total")}
         for c in candidates if c.get("start") is not None],
        key=lambda x: (x["score"] is None, -(x["score"] or 0))
    )[:10]

    dna={
        "schema_version":"1.0",
        "asset_id":asset_id,
        "source_url":asset.get("source_url"),
        "purpose":asset.get("purpose"),
        "hook":{
            "opening_duration": ((opening or {}).get("end",0) - (opening or {}).get("start",0)) if opening else None,
            "opening_text":opening_text,
            "opening_type":"statement" if opening_text else None,
            "first_meaningful_claim":opening_text or None,
        },
        "structure":{
            "intro":bool(opening),
            "setup":bool(len(transcript)>1),
            "escalation":None,
            "payoff": transcript[-1].get("text") if len(transcript)>1 else None,
            "cta_end":None,
        },
        "pacing":{
            "duration":duration,
            "scene_count":len(scenes),
            "scene_changes_per_minute":(len(scenes)/(duration/60)) if duration else None,
            "speech_density_words_per_minute":(sum(len(_words(x.get("text",""))) for x in transcript)/(duration/60)) if duration else None,
            "silence":None,
            "cuts_per_minute":None,
        },
        "text_captions":{
            "captions_present":False,
            "text_density":None,
            "opening_text":opening_text,
            "recurring_phrases":[],
        },
        "audio":{
            "speech_present":bool(transcript),
            "music_present":None,
            "loudness":None,
        },
        "visual":{
            "scene_count":len(scenes),
            "scene_duration_average":(duration/len(scenes)) if scenes else None,
            "visual_changes":len(scenes),
            "framing":None,
        },
        "moments":{
            "candidate_hooks":candidate_hooks,
            "candidate_payoffs":candidate_hooks[-3:],
            "surprising_statements":[x for x in candidate_hooks if "surpris" in x["text"].lower()][:5],
            "high_information_sections":candidate_hooks[:5],
        },
        "missing_modalities":[
            name for name,available in {
                "captions":False,
                "music_detection":False,
                "framing":False,
                "semantic_escalation":False,
            }.items() if not available
        ],
    }
    return dna

def write_reference_dna(db, asset_id):
    dna=build_reference_dna(db,asset_id)
    from .library import AssetLibrary
    path=AssetLibrary().ensure(asset_id)["dna"]/"reference_dna.json"
    path.write_text(json.dumps(dna,indent=2,ensure_ascii=False),encoding="utf-8")
    db.update_asset(asset_id, metadata={**db.get_asset(asset_id).get("metadata",{}),"reference_dna_path":str(path)})
    return dna, path
