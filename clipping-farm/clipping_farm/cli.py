import argparse, json
from .db import DB
from .worker import Worker

def main():
 p=argparse.ArgumentParser(); p.add_argument("cmd",choices=["init","demo","worker","status"]); p.add_argument("--db",default="clipping_farm.db"); a=p.parse_args(); db=DB(a.db)
 if a.cmd=="init": print(f"Initialised {a.db}")
 elif a.cmd=="demo":
  db.set_rights("demo-source","AUTHORISED",{"basis":"user-authorised fixture"})
  j1,_=db.add_job("metadata","media_agent",{"source_id":"demo-source"},idempotency_key="demo:metadata",budget=0)
  j2,_=db.add_job("analyse","analysis_agent",{"source_id":"demo-source"},idempotency_key="demo:analyse",depends_on=[j1["id"]],budget=.05)
  print(json.dumps({"jobs":[j1["id"],j2["id"]]},indent=2))
 elif a.cmd=="worker":
  w=Worker(db,capabilities=["metadata","analyse"])
  handlers={"metadata":lambda j:{"decision":"complete","actual_cost":0},"analyse":lambda j:{"decision":"complete","actual_cost":0}}
  print("processed",w.run_once(handlers))
 elif a.cmd=="status": print(json.dumps(db.status(),indent=2))
if __name__=="__main__":main()
