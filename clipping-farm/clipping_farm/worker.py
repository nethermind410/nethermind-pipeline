import socket, time, traceback
from .db import DB

class Worker:
 def __init__(self,db,worker_id=None,capabilities=None,lease_seconds=300):
  self.db=db; self.id=worker_id or f"{socket.gethostname()}-{id(self)}"; self.capabilities=capabilities or []; self.lease_seconds=lease_seconds
 def heartbeat(self):
  self.db.cx.execute("INSERT INTO workers VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,capabilities=excluded.capabilities,last_seen=excluded.last_seen",(self.id,"HEALTHY",__import__('json').dumps(self.capabilities),self.db.now()))
 def run_once(self,handlers):
  self.heartbeat(); self.db.recover_expired(); job=self.db.claim(self.id,self.lease_seconds)
  if not job:return False
  if not self.db.start(job["id"],self.id):return False
  try:
   handler=handlers.get(job["task"])
   if not handler: raise RuntimeError(f"No handler for task {job['task']}")
   result=handler(job)
   self.db.finish(job["id"],self.id,result,float(result.get("actual_cost",0)))
  except Exception as e:
   self.db.fail(job["id"],self.id,f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=3)}",True)
  return True
