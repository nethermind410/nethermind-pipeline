import json, sqlite3, time, uuid
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
 id TEXT PRIMARY KEY, parent_job_id TEXT, task TEXT NOT NULL, agent TEXT NOT NULL,
 state TEXT NOT NULL, priority INTEGER NOT NULL DEFAULT 0, payload TEXT NOT NULL,
 result TEXT, idempotency_key TEXT UNIQUE, attempts INTEGER NOT NULL DEFAULT 0,
 max_attempts INTEGER NOT NULL DEFAULT 3, lease_owner TEXT, lease_until REAL,
 depends_on TEXT NOT NULL DEFAULT '[]', budget REAL NOT NULL DEFAULT 0,
 estimated_cost REAL NOT NULL DEFAULT 0, actual_cost REAL NOT NULL DEFAULT 0,
 error TEXT, created_at REAL NOT NULL, started_at REAL, finished_at REAL
);
CREATE INDEX IF NOT EXISTS idx_jobs_ready ON jobs(state, priority DESC, created_at);
CREATE TABLE IF NOT EXISTS costs (
 id TEXT PRIMARY KEY, job_id TEXT NOT NULL, agent TEXT NOT NULL, task TEXT NOT NULL,
 model TEXT, provider TEXT, input_units REAL DEFAULT 0, output_units REAL DEFAULT 0,
 estimated_cost REAL DEFAULT 0, actual_cost REAL DEFAULT 0, currency TEXT DEFAULT 'USD',
 status TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS artifacts (
 id TEXT PRIMARY KEY, cache_key TEXT UNIQUE NOT NULL, kind TEXT NOT NULL,
 path TEXT NOT NULL, content_hash TEXT NOT NULL, metadata TEXT NOT NULL DEFAULT '{}', created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS rights (
 source_id TEXT PRIMARY KEY, state TEXT NOT NULL, evidence TEXT NOT NULL DEFAULT '{}', updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS approvals (
 job_id TEXT PRIMARY KEY, state TEXT NOT NULL, decided_at REAL, decided_by TEXT, notes TEXT
);
CREATE TABLE IF NOT EXISTS events (
 id TEXT PRIMARY KEY, job_id TEXT, event TEXT NOT NULL, data TEXT NOT NULL DEFAULT '{}', created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS workers (
 id TEXT PRIMARY KEY, status TEXT NOT NULL, capabilities TEXT NOT NULL DEFAULT '[]', last_seen REAL NOT NULL
);
"""

class DB:
    def __init__(self, path="clipping_farm.db"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.cx=sqlite3.connect(path, timeout=30, isolation_level=None)
        self.cx.row_factory=sqlite3.Row
        self.cx.execute("PRAGMA journal_mode=WAL")
        self.cx.execute("PRAGMA foreign_keys=ON")
        self.cx.executescript(SCHEMA)
    def now(self): return time.time()
    def event(self, job_id, event, data=None):
        self.cx.execute("INSERT INTO events VALUES (?,?,?,?,?)",(str(uuid.uuid4()),job_id,event,json.dumps(data or {}),self.now()))
    def add_job(self, task, agent, payload, *, idempotency_key=None, depends_on=None, priority=0, budget=0, max_attempts=3, parent_job_id=None):
        key=idempotency_key or str(uuid.uuid4())
        row=self.cx.execute("SELECT * FROM jobs WHERE idempotency_key=?",(key,)).fetchone()
        if row: return dict(row), True
        jid=str(uuid.uuid4()); now=self.now()
        self.cx.execute("INSERT INTO jobs(id,parent_job_id,task,agent,state,priority,payload,idempotency_key,max_attempts,depends_on,budget,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                        (jid,parent_job_id,task,agent,"PENDING",priority,json.dumps(payload),key,max_attempts,json.dumps(depends_on or []),budget,now))
        self.event(jid,"created",{"task":task,"agent":agent})
        return dict(self.cx.execute("SELECT * FROM jobs WHERE id=?",(jid,)).fetchone()), False
    def dependencies_ready(self,row):
        deps=json.loads(row["depends_on"] or "[]")
        if not deps: return True
        states=[self.cx.execute("SELECT state FROM jobs WHERE id=?",(d,)).fetchone() for d in deps]
        return all(r and r["state"]=="COMPLETE" for r in states)
    def promote_ready(self):
        self.cx.execute("BEGIN IMMEDIATE")
        try:
            rows=self.cx.execute("SELECT * FROM jobs WHERE state='PENDING' ORDER BY priority DESC,created_at").fetchall()
            for r in rows:
                if self.dependencies_ready(r):
                    self.cx.execute("UPDATE jobs SET state='READY' WHERE id=? AND state='PENDING'",(r["id"],))
                    self.event(r["id"],"ready")
            self.cx.execute("COMMIT")
        except Exception:
            self.cx.execute("ROLLBACK"); raise
    def claim(self, worker_id, lease_seconds=300, capabilities=None):
        now=self.now(); until=now+lease_seconds; caps=set(capabilities or [])
        self.cx.execute("BEGIN IMMEDIATE")
        try:
            rows=self.cx.execute("SELECT * FROM jobs WHERE state IN ('PENDING','READY') ORDER BY priority DESC,created_at").fetchall()
            row=None
            for candidate in rows:
                if not self.dependencies_ready(candidate): continue
                if caps and candidate["task"] not in caps: continue
                row=candidate; break
            if not row: self.cx.execute("COMMIT"); return None
            cur=self.cx.execute("UPDATE jobs SET state='CLAIMED',lease_owner=?,lease_until=?,attempts=attempts+1,started_at=? WHERE id=? AND state IN ('PENDING','READY')",
                                (worker_id,until,now,row["id"]))
            if cur.rowcount != 1:
                self.cx.execute("COMMIT"); return None
            self.event(row["id"],"claimed",{"worker":worker_id,"lease_until":until})
            self.cx.execute("COMMIT")
            return dict(self.cx.execute("SELECT * FROM jobs WHERE id=?",(row["id"],)).fetchone())
        except Exception:
            self.cx.execute("ROLLBACK"); raise
    def start(self,jid,worker_id):
        cur=self.cx.execute("UPDATE jobs SET state='RUNNING' WHERE id=? AND state='CLAIMED' AND lease_owner=?",(jid,worker_id))
        if cur.rowcount==1: self.event(jid,"started",{"worker":worker_id})
        return cur.rowcount==1
    def finish(self,jid,worker_id,result,actual_cost=0):
        cur=self.cx.execute("UPDATE jobs SET state='COMPLETE',result=?,actual_cost=?,finished_at=?,lease_owner=NULL,lease_until=NULL WHERE id=? AND state IN ('CLAIMED','RUNNING') AND lease_owner=?",
                            (json.dumps(result),actual_cost,self.now(),jid,worker_id))
        if cur.rowcount!=1: raise RuntimeError(f"job {jid} no longer owned by {worker_id}")
        self.event(jid,"complete",{"actual_cost":actual_cost})
    def fail(self,jid,worker_id,error,retryable=True):
        row=self.cx.execute("SELECT attempts,max_attempts,state FROM jobs WHERE id=? AND lease_owner=?",(jid,worker_id)).fetchone()
        if not row: return False
        state="READY" if retryable and row["attempts"]<row["max_attempts"] else "DEAD_LETTER"
        self.cx.execute("UPDATE jobs SET state=?,error=?,lease_owner=NULL,lease_until=NULL WHERE id=? AND lease_owner=?",
                        (state,error,jid,worker_id))
        self.event(jid,"failed",{"error":error,"retryable":retryable,"state":state})
        return True
    def recover_expired(self):
        now=self.now(); rows=self.cx.execute("SELECT id,attempts,max_attempts FROM jobs WHERE state IN ('CLAIMED','RUNNING') AND lease_until<?",(now,)).fetchall()
        for r in rows:
            state="READY" if r["attempts"]<r["max_attempts"] else "DEAD_LETTER"
            self.cx.execute("UPDATE jobs SET state=?,lease_owner=NULL,lease_until=NULL,error=? WHERE id=? AND state IN ('CLAIMED','RUNNING')",
                            (state,"worker lease expired",r["id"]))
            self.event(r["id"],"lease_expired",{"state":state})
    def put_artifact(self,cache_key,kind,path,content_hash,metadata=None):
        row=self.cx.execute("SELECT * FROM artifacts WHERE cache_key=?",(cache_key,)).fetchone()
        if row:return dict(row),True
        aid=str(uuid.uuid4())
        self.cx.execute("INSERT INTO artifacts VALUES(?,?,?,?,?,?,?)",(aid,cache_key,kind,path,content_hash,json.dumps(metadata or {}),self.now()))
        return dict(self.cx.execute("SELECT * FROM artifacts WHERE id=?",(aid,)).fetchone()),False
    def get_artifact(self,cache_key):
        r=self.cx.execute("SELECT * FROM artifacts WHERE cache_key=?",(cache_key,)).fetchone()
        return dict(r) if r else None
    def set_rights(self,source_id,state,evidence=None):
        if state not in {"UNKNOWN","PENDING","AUTHORISED","REJECTED","EXPIRED"}: raise ValueError(state)
        self.cx.execute("INSERT INTO rights VALUES(?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET state=excluded.state,evidence=excluded.evidence,updated_at=excluded.updated_at",
                        (source_id,state,json.dumps(evidence or {}),self.now()))
    def rights(self,source_id):
        r=self.cx.execute("SELECT * FROM rights WHERE source_id=?",(source_id,)).fetchone()
        return dict(r) if r else None
    def approve(self,jid,approved,by="user",notes=""):
        self.cx.execute("INSERT OR REPLACE INTO approvals VALUES(?,?,?,?,?)",(jid,"APPROVED" if approved else "REJECTED",self.now(),by,notes))
    def approval(self,jid):
        r=self.cx.execute("SELECT * FROM approvals WHERE job_id=?",(jid,)).fetchone()
        return dict(r) if r else None
    def status(self):
        return [dict(r) for r in self.cx.execute("SELECT id,task,agent,state,attempts,actual_cost,error FROM jobs ORDER BY created_at DESC LIMIT 50")]
