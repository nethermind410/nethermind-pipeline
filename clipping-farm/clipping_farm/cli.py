import argparse, json
from .db import DB
from .worker import Worker
from .pipeline import ClippingPipeline
from .agent_handlers import LocalHandlers
from .ingest import Source, SourceIngestor
from .reference import ReferenceInspector
from .runner import PipelineRunner

TASKS=["metadata","analyse_audio","analyse_scenes","transcribe","generate_candidates","score_candidates","select_candidates","produce_clips","qc","repair","export_review"]

def main():
    p=argparse.ArgumentParser()
    p.add_argument("cmd",choices=["init","demo","plan","run","worker","status","ingest","source","reference","artifact"])
    p.add_argument("--db",default="clipping_farm.db")
    p.add_argument("--source-id",default="demo-source")
    p.add_argument("--source-path")
    p.add_argument("--budget",type=float,default=0.0)
    p.add_argument("--kind",default="file")
    p.add_argument("--url")
    p.add_argument("--cache-key")
    a=p.parse_args(); db=DB(a.db)
    if a.cmd=="init":
        print(f"Initialised {a.db}")

    elif a.cmd=="ingest":
        if not a.source_path:
            p.error("ingest requires --source-path")
        source = Source(
            source_id=a.source_id,
            location=a.source_path,
            kind=a.kind,
        )
        result = SourceIngestor(db).ingest_file(source)
        print(json.dumps(result, indent=2))

    elif a.cmd=="artifact":
        if not a.cache_key:
            p.error("artifact requires --cache-key")

        result = db.get_artifact(a.cache_key)
        if result is None:
            raise SystemExit(f"Artifact not found: {a.cache_key}")

        result["verification"] = db.verify_artifact(a.cache_key)
        print(json.dumps(result, indent=2))

    elif a.cmd=="source":
        result = SourceIngestor(db).get_source(a.source_id)
        if result is None:
            raise SystemExit(f"Source not found: {a.source_id}")
        print(json.dumps(result, indent=2))

    elif a.cmd=="reference":
        if not a.url:
            p.error("reference requires --url")

        inspector = ReferenceInspector()
        result = inspector.inspect(a.url)
        persisted = inspector.persist(db, result)

        print(json.dumps(persisted, indent=2))

    elif a.cmd in ("demo","plan"):
        if a.cmd=="demo": db.set_rights(a.source_id,"AUTHORISED",{"basis":"user-authorised fixture"})
        plan=ClippingPipeline(db).create(a.source_id,source_path=a.source_path,budget=a.budget)
        print(json.dumps(plan.jobs if a.cmd=="plan" else {"source_id":a.source_id,"jobs":plan.jobs},indent=2))
    elif a.cmd=="run":
        if not a.source_id:
            p.error("run requires --source-id")

        if not a.source_path:
            p.error("run requires --source-path")

        db.set_rights(
            a.source_id,
            "AUTHORISED",
            {"basis": "user-authorised local source"},
        )

        plan = ClippingPipeline(db).create(
            a.source_id,
            source_path=a.source_path,
            budget=a.budget,
        )

        handlers = LocalHandlers(db).handlers()

        runner = PipelineRunner(
            db,
            handlers,
            capabilities=TASKS,
        )

        result = runner.run(
            plan.source_id,
            plan.jobs,
        )

        print(json.dumps({
            "source_id": result.source_id,
            "state": result.state,
            "processed": result.processed,
            "jobs": result.jobs,
        }, indent=2))

        if result.state != "COMPLETE":
            raise SystemExit(1)

    elif a.cmd=="worker":
        h=LocalHandlers(db)
        w=Worker(db,capabilities=TASKS)
        print("processed",w.run_once(h.handlers()))
    elif a.cmd=="status": print(json.dumps(db.status(),indent=2))

if __name__=="__main__": main()
