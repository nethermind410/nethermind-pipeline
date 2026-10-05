"""Provider health state used to prevent repeated calls to a broken adapter."""
from dataclasses import dataclass
import time

@dataclass
class Health:
    state:str="HEALTHY"
    failures:int=0
    last_error:str=""
    retry_after:float=0.0

class ProviderHealth:
    def __init__(self, cooldown_seconds=30):
        self.cooldown_seconds=cooldown_seconds
        self.states={}
    def state(self,name):
        h=self.states.setdefault(name,Health())
        if h.state=="DEGRADED" and time.time() >= h.retry_after:
            h.state="HEALTHY"
        return h.state
    def available(self,name):
        return self.state(name) == "HEALTHY"
    def success(self,name):
        self.states[name]=Health("HEALTHY")
    def failure(self,name,error):
        h=self.states.setdefault(name,Health())
        h.failures+=1; h.last_error=str(error)
        if h.failures>=2:
            h.state="DEGRADED"; h.retry_after=time.time()+self.cooldown_seconds
        self.states[name]=h
