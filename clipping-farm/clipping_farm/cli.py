import argparse, json
from .db import DB
from .worker import Worker
from .pipeline import ClippingPipeline
from .agent_handlers import LocalHandlers

TASKS=["metadata","analyse_audio","analyse_scenes","transcribe","generate_candidates","score_candidates","select_candidates","produce_clips","qc","repair","export_review"]

def main():
    p=argparse.ArgumentParser()
    p.add_argument("cmd",choices=["init","demo","plan","worker","status"])
    p.add_argument("--db",default="clipping_farm.db")
    p.add_argument("--source-id",default="demo-source")
    p.add_argument("--source-path")
    p.add_argument("--budget",type=float,default=0.0)
    a=p.parse_args(); db=DB(a.db)
    if a.cmd=="init": print(f"Initialised {a.db}")
    elif a.cmd in ("demo","plan"):
        if a.cmd=="demo": db.set_rights(a.source_id,"AUTHORISED",{"basis":"user-authorised fixture"})
        plan=ClippingPipeline(db).create(a.source_id,source_path=a.source_path,budget=a.budget)
        print(json.dumps(plan.jobs if a.cmd=="plan" else {"source_id":a.source_id,"jobs":plan.jobs},indent=2))
    elif a.cmd=="worker":
        h=LocalHandlers(db)
        w=Worker(db,capabilities=TASKS)
        print("processed",w.run_once(h.handlers()))
    elif a.cmd=="status": print(json.dumps(db.status(),indent=2))

if __name__=="__main__": main()
