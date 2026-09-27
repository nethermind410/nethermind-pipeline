import hashlib, uuid
from .db import DB
class RightsGate:
 def __init__(self,db): self.db=db
 def check(self,source_id):
  r=self.db.rights(source_id)
  if not r or r["state"]!="AUTHORISED": raise PermissionError(f"Source {source_id} is not AUTHORISED")
class Budget:
 def __init__(self,db): self.db=db
 def reserve(self,job_id,amount,budget):
  if amount<0: raise ValueError("negative reservation")
  spent=self.db.cx.execute("SELECT COALESCE(SUM(estimated_cost),0) x FROM costs WHERE job_id=? AND status IN ('RESERVED','SPENT')",(job_id,)).fetchone()["x"]
  if spent+amount>budget: raise RuntimeError(f"Budget blocked: {spent+amount:.6f} > {budget:.6f}")
  reservation_id=uuid.uuid4().hex
  self.db.cx.execute(
   "INSERT INTO costs(id,job_id,agent,task,model,provider,input_units,output_units,estimated_cost,actual_cost,currency,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
   (reservation_id,job_id,"harness","reserve",None,None,0,0,amount,0,"USD","RESERVED",self.db.now()))
  return reservation_id

 def settle(self,reservation_id,actual_cost):
  if actual_cost < 0: raise ValueError("negative actual cost")
  cur=self.db.cx.execute(
   "UPDATE costs SET actual_cost=?,status='SPENT' WHERE id=? AND status='RESERVED'",
   (actual_cost,reservation_id))
  if cur.rowcount != 1: raise RuntimeError(f"reservation {reservation_id} is not open")
  return True
class ModelRouter:
 DETERMINISTIC={"silence_detection","scene_detection","metadata","hash","duplicate_detection","audio_levels","frame_sampling"}
 def __init__(self,db): self.db=db
 def route(self,task,quality_required=0.0,budget=0.0,input_hash="",modality="text",required_capability=None):
  key=self.cache_key(task,quality_required,input_hash,modality,required_capability); cached=self.db.get_artifact(key)
  if cached:return {"method":"cache","model":None,"cache":cached,"estimated_cost":0.0,"reason":"artifact cache hit"}
  if task in self.DETERMINISTIC:return {"method":"deterministic","model":None,"estimated_cost":0.0,"reason":"deterministic tool available"}
  if budget<=0:return {"method":"blocked","model":None,"estimated_cost":0.0,"reason":"no paid budget available"}
  if quality_required<.70 and budget<=.05:return {"method":"cheap","model":"cheap-default","estimated_cost":.005,"reason":"cheap tier"}
  if quality_required<.90:return {"method":"cheap","model":"cheap-default","estimated_cost":.01,"reason":"cheap tier"}
  return {"method":"premium","model":"premium-default","estimated_cost":.05,"reason":"higher confidence required"}
 def cache_key(self,task,quality,input_hash,modality,capability=None):
  return hashlib.sha256(f"{task}|{quality:.3f}|{input_hash}|{modality}|{capability or ''}".encode()).hexdigest()
 def escalate(self,confidence,required): return confidence<required
class Harness:
 def __init__(self,db): self.db=db; self.rights=RightsGate(db); self.budget=Budget(db); self.router=ModelRouter(db)
