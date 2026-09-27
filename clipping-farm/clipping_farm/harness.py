import hashlib, json
from .db import DB

class RightsGate:
 def __init__(self,db): self.db=db
 def check(self,source_id):
  r=self.db.rights(source_id)
  if not r or r["state"]!="AUTHORISED": raise PermissionError(f"Source {source_id} is not AUTHORISED")

class Budget:
 def __init__(self,db): self.db=db
 def reserve(self,job_id,amount,budget):
  spent=self.db.cx.execute("SELECT COALESCE(SUM(estimated_cost),0) x FROM costs WHERE job_id=? AND status IN ('RESERVED','SPENT')",(job_id,)).fetchone()["x"]
  if spent+amount>budget: raise RuntimeError(f"Budget blocked: {spent+amount:.6f} > {budget:.6f}")
  self.db.cx.execute("INSERT INTO costs VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(__import__('uuid').uuid4().hex,job_id,"harness","reserve",None,None,0,0,amount,0,"USD","RESERVED",self.db.now()))
 def settle(self,job_id,actual):
  self.db.cx.execute("UPDATE costs SET status='SPENT',actual_cost=? WHERE id=(SELECT id FROM costs WHERE job_id=? AND status='RESERVED' ORDER BY created_at DESC LIMIT 1)",(actual,job_id))

class ModelRouter:
 def __init__(self,db): self.db=db
 def route(self,task,quality_required=0.0,budget=0.0,input_hash="",modality="text"):
  key=self.cache_key(task,quality_required,input_hash,modality)
  cached=self.db.get_artifact(key)
  if cached:return {"method":"cache","model":None,"cache":cached,"estimated_cost":0.0}
  deterministic={"silence_detection","scene_detection","metadata","hash","duplicate_detection","audio_levels"}
  if task in deterministic:return {"method":"deterministic","model":None,"estimated_cost":0.0}
  if quality_required<0.70 and budget<=0.05:return {"method":"cheap","model":"cheap-default","estimated_cost":0.005}
  if quality_required<0.90:return {"method":"cheap","model":"cheap-default","estimated_cost":0.01}
  return {"method":"premium","model":"premium-default","estimated_cost":0.05}
 def cache_key(self,task,quality,input_hash,modality): return hashlib.sha256(f"{task}|{quality:.3f}|{input_hash}|{modality}".encode()).hexdigest()
 def escalate(self,confidence,required): return confidence<required

class Harness:
 def __init__(self,db): self.db=db; self.rights=RightsGate(db); self.budget=Budget(db); self.router=ModelRouter(db)
