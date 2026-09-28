"""Learning Brain v1: immutable evidence, deterministic learning, calibration and experiments.

Learning changes future decisions only. Historical evidence is append-only.
"""
from __future__ import annotations
import hashlib, json, math, statistics, time, uuid
from dataclasses import dataclass, asdict

ALGORITHM_VERSION="learning-v1"
FEATURE_VERSION="features-v1"
OUTCOME_VERSION="outcome-v1"
CALIBRATION_VERSION="calibration-v1"

SCHEMA="""
CREATE TABLE IF NOT EXISTS performance_records(
 id TEXT PRIMARY KEY, clip_id TEXT NOT NULL, platform TEXT NOT NULL, account_id TEXT,
 observed_at REAL NOT NULL, views REAL, watch_time_seconds REAL,
 average_view_duration_seconds REAL, retention_percent REAL, completion_rate REAL,
 likes REAL, comments REAL, shares REAL, saves REAL, followers_gained REAL,
 impressions REAL, click_through_rate REAL, observation_window_hours REAL NOT NULL,
 source TEXT, source_reference TEXT, metrics_version TEXT NOT NULL, created_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS idx_perf_clip ON performance_records(clip_id);
CREATE TABLE IF NOT EXISTS performance_outcomes(
 id TEXT PRIMARY KEY, clip_id TEXT NOT NULL, platform TEXT NOT NULL,
 window_hours REAL NOT NULL, normalised_performance REAL, performance_percentile REAL,
 view_rate REAL, retention_score REAL, completion_score REAL, engagement_score REAL,
 share_score REAL, follow_score REAL, outcome_version TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS feature_snapshots(
 id TEXT PRIMARY KEY, clip_id TEXT NOT NULL, candidate_id TEXT, feature_version TEXT NOT NULL,
 hook_score REAL, payoff_score REAL, context_score REAL, emotion_score REAL,
 information_score REAL, visual_score REAL, audio_score REAL, standalone_score REAL,
 novelty_score REAL, duration_seconds REAL, opening_type TEXT, ending_type TEXT,
 caption_style TEXT, crop_type TEXT, topic TEXT, source_type TEXT, model_version TEXT,
 prompt_version TEXT, scoring_version TEXT, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS learning_runs(
 id TEXT PRIMARY KEY, started_at REAL NOT NULL, completed_at REAL, data_cutoff REAL NOT NULL,
 observation_window REAL, feature_version TEXT, scoring_version TEXT, algorithm_version TEXT NOT NULL,
 strategy_version TEXT, records_considered INTEGER NOT NULL DEFAULT 0,
 records_excluded INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL, summary TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS patterns(
 id TEXT PRIMARY KEY, pattern_type TEXT NOT NULL, feature_name TEXT NOT NULL,
 operator TEXT NOT NULL, threshold REAL, segment_definition TEXT NOT NULL,
 sample_size INTEGER NOT NULL, mean_performance REAL, median_performance REAL,
 baseline_performance REAL, effect_size REAL, confidence REAL NOT NULL, stability REAL NOT NULL,
 status TEXT NOT NULL, first_observed_at REAL NOT NULL, last_updated_at REAL NOT NULL,
 learning_run_id TEXT NOT NULL, algorithm_version TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS strategy_recommendations(
 id TEXT PRIMARY KEY, type TEXT NOT NULL, target TEXT NOT NULL, current_value TEXT,
 proposed_value TEXT, expected_effect REAL, confidence REAL NOT NULL, sample_size INTEGER NOT NULL,
 stability REAL NOT NULL, supporting_patterns TEXT NOT NULL, learning_run_id TEXT NOT NULL,
 algorithm_version TEXT NOT NULL, feature_version TEXT NOT NULL, status TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS experiments(
 id TEXT PRIMARY KEY, name TEXT NOT NULL, hypothesis TEXT NOT NULL, control_strategy TEXT NOT NULL,
 test_strategy TEXT NOT NULL, allocation_control REAL NOT NULL, allocation_test REAL NOT NULL,
 target_metric TEXT NOT NULL, minimum_sample INTEGER NOT NULL, minimum_duration REAL NOT NULL,
 status TEXT NOT NULL, created_at REAL NOT NULL, started_at REAL, ended_at REAL);
CREATE TABLE IF NOT EXISTS experiment_assignments(
 id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL, clip_id TEXT NOT NULL, variant TEXT NOT NULL,
 strategy_version TEXT NOT NULL, assigned_at REAL NOT NULL, assignment_method TEXT NOT NULL,
 assignment_hash TEXT NOT NULL, UNIQUE(experiment_id,clip_id));
CREATE TABLE IF NOT EXISTS experiment_results(
 id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL, learning_run_id TEXT, control_n INTEGER NOT NULL,
 test_n INTEGER NOT NULL, control_mean REAL, test_mean REAL, control_median REAL,
 test_median REAL, difference REAL, relative_difference REAL, confidence REAL NOT NULL,
 status TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS strategy_versions(
 id TEXT PRIMARY KEY, version TEXT UNIQUE NOT NULL, parent_version TEXT, status TEXT NOT NULL,
 created_at REAL NOT NULL, activated_at REAL, deactivated_at REAL, created_by TEXT NOT NULL,
 change_summary TEXT NOT NULL, recommendation_ids TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS calibration_records(
 id TEXT PRIMARY KEY, learning_run_id TEXT NOT NULL, score_band TEXT NOT NULL,
 sample_size INTEGER NOT NULL, predicted_mean REAL, observed_mean REAL,
 absolute_error REAL, calibration_error REAL, method TEXT NOT NULL, status TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS perf_immutable_update BEFORE UPDATE ON performance_records
BEGIN SELECT RAISE(ABORT,'performance_records are immutable'); END;
CREATE TRIGGER IF NOT EXISTS perf_immutable_delete BEFORE DELETE ON performance_records
BEGIN SELECT RAISE(ABORT,'performance_records are immutable'); END;
CREATE TRIGGER IF NOT EXISTS features_immutable_update BEFORE UPDATE ON feature_snapshots
BEGIN SELECT RAISE(ABORT,'feature_snapshots are immutable'); END;
CREATE TRIGGER IF NOT EXISTS features_immutable_delete BEFORE DELETE ON feature_snapshots
BEGIN SELECT RAISE(ABORT,'feature_snapshots are immutable'); END;
"""

@dataclass(frozen=True)
class Pattern:
    feature_name:str; segment_definition:str; sample_size:int
    mean_performance:float; median_performance:float; baseline_performance:float
    effect_size:float; confidence:float; stability:float; status:str

class LearningStore:
    def __init__(self,db):
        self.db=db; self.cx=db.cx; self.cx.executescript(SCHEMA)
    def _now(self): return time.time()
    def add_performance(self,*,clip_id,platform,observation_window_hours,views=None,
        watch_time_seconds=None,average_view_duration_seconds=None,retention_percent=None,
        completion_rate=None,likes=None,comments=None,shares=None,saves=None,
        followers_gained=None,impressions=None,click_through_rate=None,account_id=None,
        observed_at=None,source="manual",source_reference=None,metrics_version="metrics-v1"):
        rid=str(uuid.uuid4())
        self.cx.execute("""INSERT INTO performance_records VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (rid,clip_id,platform,account_id,observed_at or self._now(),views,watch_time_seconds,
             average_view_duration_seconds,retention_percent,completion_rate,likes,comments,shares,
             saves,followers_gained,impressions,click_through_rate,observation_window_hours,
             source,source_reference,metrics_version,self._now()))
        return rid
    def add_outcome(self,*,clip_id,platform,window_hours,normalised_performance=None,
                    performance_percentile=None,view_rate=None,retention_score=None,
                    completion_score=None,engagement_score=None,share_score=None,follow_score=None):
        oid=str(uuid.uuid4())
        self.cx.execute("""INSERT INTO performance_outcomes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (oid,clip_id,platform,window_hours,normalised_performance,performance_percentile,
             view_rate,retention_score,completion_score,engagement_score,share_score,follow_score,
             OUTCOME_VERSION,self._now()))
        return oid
    def add_features(self,*,clip_id,candidate_id=None,feature_version=FEATURE_VERSION,
        hook_score=None,payoff_score=None,context_score=None,emotion_score=None,
        information_score=None,visual_score=None,audio_score=None,standalone_score=None,
        novelty_score=None,duration_seconds=None,opening_type=None,ending_type=None,
        caption_style=None,crop_type=None,topic=None,source_type=None,model_version=None,
        prompt_version=None,scoring_version=None):
        fid=str(uuid.uuid4())
        self.cx.execute("""INSERT INTO feature_snapshots VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (fid,clip_id,candidate_id,feature_version,hook_score,payoff_score,context_score,
             emotion_score,information_score,visual_score,audio_score,standalone_score,novelty_score,
             duration_seconds,opening_type,ending_type,caption_style,crop_type,topic,source_type,
             model_version,prompt_version,scoring_version,self._now()))
        return fid
    def latest_features(self,clip_id):
        r=self.cx.execute("SELECT * FROM feature_snapshots WHERE clip_id=? ORDER BY created_at DESC LIMIT 1",(clip_id,)).fetchone()
        return dict(r) if r else None
    def performance_snapshots(self,clip_id):
        return [dict(r) for r in self.cx.execute("SELECT * FROM performance_records WHERE clip_id=? ORDER BY observed_at",(clip_id,))]

class LearningBrain:
    SAMPLE_OBSERVATION=10; SAMPLE_PROMISING=30; SAMPLE_SUPPORTED=100; SAMPLE_STRONG=250
    def __init__(self,db): self.db=db; self.store=LearningStore(db)
    @staticmethod
    def _confidence(n,effect,stability):
        return round(max(0,min(1,(1-math.exp(-n/100))*min(1,abs(effect)/.30)*stability)),4)
    @staticmethod
    def _status(n,confidence,stability):
        if n<10:return "INSUFFICIENT_DATA"
        if n<30:return "OBSERVED"
        if n<100:return "PROMISING"
        if n<250:return "SUPPORTED"
        return "VALIDATED" if confidence>=.65 and stability>=.60 else "SUPPORTED"
    @staticmethod
    def _stability(values):
        if len(values)<3:return 0.0
        overall=statistics.mean(values)
        if not overall:return 0.0
        size=max(1,len(values)//3); chunks=[values[:size],values[size:2*size],values[2*size:]]
        effects=[statistics.mean(c)/overall-1 for c in chunks if c]
        return round(max(0,min(1,1-statistics.pstdev(effects)/.25)),4) if len(effects)>1 else 0.0
    def _joined(self):
        return [dict(r) for r in self.db.cx.execute(
            """SELECT f.*,o.platform,o.window_hours,o.normalised_performance,o.performance_percentile
               FROM feature_snapshots f JOIN performance_outcomes o ON o.clip_id=f.clip_id
               WHERE o.normalised_performance IS NOT NULL""")]
    def create_outcomes_from_performance(self):
        rows=self.db.cx.execute("SELECT * FROM performance_records ORDER BY observed_at").fetchall()
        cohorts={}
        for r in rows: cohorts.setdefault((r["platform"],r["account_id"],r["observation_window_hours"]),[]).append(r)
        for rs in cohorts.values():
            vals=[float(r["views"]) for r in rs if r["views"] is not None]
            if not vals: continue
            med=max(statistics.median(vals),1)
            ordered=sorted(vals)
            for r in rs:
                if r["views"] is None: continue
                v=float(r["views"]); percentile=sum(x<=v for x in ordered)/len(ordered)
                retention=float(r["retention_percent"] or 0)/100*.25
                completion=float(r["completion_rate"] or 0)/100*.20
                norm=(v/med)*.55+retention+completion
                self.store.add_outcome(clip_id=r["clip_id"],platform=r["platform"],
                    window_hours=r["observation_window_hours"],normalised_performance=norm,
                    performance_percentile=percentile,
                    view_rate=(v/r["impressions"] if r["impressions"] else None),
                    retention_score=retention,completion_score=completion,
                    engagement_score=sum(float(r[k] or 0) for k in ("likes","comments","shares","saves")),
                    share_score=float(r["shares"] or 0),follow_score=float(r["followers_gained"] or 0))
    def discover_patterns(self,run_id):
        rows=self._joined(); out=[]
        for feature in ("hook_score","payoff_score","context_score","emotion_score",
                        "information_score","visual_score","audio_score","standalone_score",
                        "novelty_score","duration_seconds"):
            vals=[r for r in rows if r.get(feature) is not None]
            if len(vals)<10: continue
            baseline=statistics.mean(float(r["normalised_performance"]) for r in vals)
            groups=[("<=30",lambda r:float(r[feature])<=30),(">30",lambda r:float(r[feature])>30)] if feature=="duration_seconds" else [
                (">=0.8",lambda r:float(r[feature])>=.8),("<0.8",lambda r:float(r[feature])<.8)]
            for segment,pred in groups:
                g=[r for r in vals if pred(r)]
                if len(g)<10: continue
                perf=[float(r["normalised_performance"]) for r in g]
                mean=statistics.mean(perf); effect=(mean-baseline)/baseline if baseline else 0
                stability=self._stability(perf); confidence=self._confidence(len(g),effect,stability)
                status=self._status(len(g),confidence,stability); now=time.time()
                self.db.cx.execute("""INSERT INTO patterns VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (str(uuid.uuid4()),"association",feature,">=",0.8 if segment==">=0.8" else (30 if segment==">30" else 0),
                     segment,len(g),mean,statistics.median(perf),baseline,effect,confidence,stability,status,
                     now,now,run_id,ALGORITHM_VERSION))
                out.append(Pattern(feature,segment,len(g),mean,statistics.median(perf),baseline,effect,confidence,stability,status))
        return out
    def calibrate(self,run_id):
        rows=self._joined()
        if not rows:return {"status":"INSUFFICIENT_DATA","sample_size":0}
        bands=[]
        for i in range(10):
            lo=i/10; hi=(i+1)/10
            g=[r for r in rows if r.get("standalone_score") is not None and lo<=float(r["standalone_score"])<(hi if i<9 else 1.01)]
            if not g:continue
            predicted=statistics.mean(float(r["standalone_score"]) for r in g)
            observed=statistics.mean(float(r["normalised_performance"]) for r in g)
            err=abs(predicted-observed)
            status="DIAGNOSTIC_ONLY" if len(rows)<1000 else ("OVERCONFIDENT" if predicted>observed+.10 else "OK")
            self.db.cx.execute("INSERT INTO calibration_records VALUES(?,?,?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()),run_id,f"{lo:.1f}-{hi:.1f}",len(g),predicted,observed,err,err,
                 CALIBRATION_VERSION,status))
            bands.append({"band":f"{lo:.1f}-{hi:.1f}","n":len(g),"predicted":predicted,"observed":observed,"error":err})
        status="DIAGNOSTIC_ONLY" if len(rows)<100 else "CALIBRATED"
        if len(rows)>=100 and any(b["predicted"]>b["observed"]+.10 for b in bands):status="OVERCONFIDENT_HIGH_SCORE_RANGE"
        return {"status":status,"sample_size":len(rows),"bands":bands}
    def recommend(self,run_id,patterns):
        ids=[]
        for p in patterns:
            if p.status not in ("SUPPORTED","VALIDATED") or p.effect_size<=0 or p.confidence<.60 or p.stability<.50:continue
            rid=str(uuid.uuid4())
            self.db.cx.execute("""INSERT INTO strategy_recommendations VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (rid,"feature_association",p.feature_name,p.segment_definition,p.segment_definition,
                 p.effect_size,p.confidence,p.sample_size,p.stability,json.dumps([p.feature_name]),
                 run_id,ALGORITHM_VERSION,FEATURE_VERSION,"PROPOSED",time.time()))
            ids.append(rid)
        return ids
    def create_strategy(self,recommendation_ids,created_by="learning-brain"):
        latest=self.db.cx.execute("SELECT version FROM strategy_versions ORDER BY created_at DESC LIMIT 1").fetchone()
        parent=latest["version"] if latest else None
        number=int(parent.rsplit("-",1)[-1])+1 if parent and parent.rsplit("-",1)[-1].isdigit() else 1
        version=f"strategy-{number}"
        self.db.cx.execute("UPDATE strategy_versions SET status='SUPERSEDED',deactivated_at=? WHERE status='ACTIVE'",(time.time(),))
        self.db.cx.execute("INSERT INTO strategy_versions VALUES(?,?,?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()),version,parent,"ACTIVE",time.time(),time.time(),None,created_by,"Learning Brain recommendation activation",json.dumps(recommendation_ids)))
        return version
    def create_experiment(self,*,name,hypothesis,control_strategy,test_strategy,target_metric="normalised_performance",
                          minimum_sample=100,minimum_duration=24,allocation_control=.8,allocation_test=.2):
        if abs(allocation_control+allocation_test-1)>.00001:raise ValueError("allocations must sum to 1")
        eid=str(uuid.uuid4())
        self.db.cx.execute("INSERT INTO experiments VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (eid,name,hypothesis,control_strategy,test_strategy,allocation_control,allocation_test,target_metric,
             minimum_sample,minimum_duration,"PROPOSED",time.time(),None,None))
        return eid
    @staticmethod
    def assign(experiment_id,clip_id,control_allocation=.8):
        digest=hashlib.sha256(f"{experiment_id}:{clip_id}".encode()).hexdigest()
        unit=int(digest[:16],16)/float(16**16)
        return ("CONTROL" if unit<control_allocation else "TEST"),digest
    def assign_clip(self,experiment_id,clip_id,strategy_version="strategy-1"):
        e=self.db.cx.execute("SELECT * FROM experiments WHERE id=?",(experiment_id,)).fetchone()
        if not e:raise KeyError(experiment_id)
        old=self.db.cx.execute("SELECT * FROM experiment_assignments WHERE experiment_id=? AND clip_id=?",(experiment_id,clip_id)).fetchone()
        if old:return dict(old)
        variant,digest=self.assign(experiment_id,clip_id,e["allocation_control"]); aid=str(uuid.uuid4())
        self.db.cx.execute("INSERT INTO experiment_assignments VALUES(?,?,?,?,?,?,?,?)",
            (aid,experiment_id,clip_id,variant,strategy_version,time.time(),"sha256",digest))
        return dict(self.db.cx.execute("SELECT * FROM experiment_assignments WHERE id=?",(aid,)).fetchone())
    def experiment_result(self,experiment_id,learning_run_id=None):
        e=self.db.cx.execute("SELECT * FROM experiments WHERE id=?",(experiment_id,)).fetchone()
        if not e:raise KeyError(experiment_id)
        rows=self.db.cx.execute("""SELECT a.variant,o.normalised_performance FROM experiment_assignments a
            JOIN performance_outcomes o ON o.clip_id=a.clip_id WHERE a.experiment_id=? AND o.normalised_performance IS NOT NULL""",(experiment_id,)).fetchall()
        c=[float(r["normalised_performance"]) for r in rows if r["variant"]=="CONTROL"]; t=[float(r["normalised_performance"]) for r in rows if r["variant"]=="TEST"]
        n=min(len(c),len(t)); cm=statistics.mean(c) if c else None; tm=statistics.mean(t) if t else None
        diff=(tm-cm) if cm is not None and tm is not None else None; rel=(diff/cm if cm else None) if diff is not None else None
        conf=0 if n<e["minimum_sample"] else min(1,1-math.exp(-n/100))*min(1,abs(rel or 0)/.30)
        status="INSUFFICIENT_DATA" if n<e["minimum_sample"] else ("NO_CLEAR_DIFFERENCE" if abs(rel or 0)<.05 else ("PROMISING" if conf<.65 else "SUPPORTED"))
        rid=str(uuid.uuid4())
        self.db.cx.execute("INSERT INTO experiment_results VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (rid,experiment_id,learning_run_id,len(c),len(t),cm,tm,statistics.median(c) if c else None,
             statistics.median(t) if t else None,diff,rel,conf,status,time.time()))
        return dict(self.db.cx.execute("SELECT * FROM experiment_results WHERE id=?",(rid,)).fetchone())
    def rollback(self,version):
        if not self.db.cx.execute("SELECT 1 FROM strategy_versions WHERE version=?",(version,)).fetchone():raise KeyError(version)
        self.db.cx.execute("UPDATE strategy_versions SET status='ROLLED_BACK',deactivated_at=? WHERE status='ACTIVE'",(time.time(),))
        self.db.cx.execute("UPDATE strategy_versions SET status='ACTIVE',activated_at=? WHERE version=?",(time.time(),version))
        return version
    def run(self,*,data_cutoff=None,observation_window=None,scoring_version=None):
        now=time.time(); run_id="LR-"+uuid.uuid4().hex[:10]
        self.db.cx.execute("INSERT INTO learning_runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_id,now,None,data_cutoff or now,observation_window,FEATURE_VERSION,scoring_version,ALGORITHM_VERSION,None,0,0,"RUNNING",""))
        self.create_outcomes_from_performance(); rows=self._joined(); considered=len(rows)
        patterns=self.discover_patterns(run_id) if considered>=10 else []
        calibration=self.calibrate(run_id) if considered else {"status":"INSUFFICIENT_DATA","sample_size":0}
        recommendations=self.recommend(run_id,patterns); strategy=self.create_strategy(recommendations) if recommendations else None
        if strategy:self.db.cx.execute("UPDATE learning_runs SET strategy_version=? WHERE id=?",(strategy,run_id))
        status="COMPLETE" if considered>=10 else "INSUFFICIENT_DATA"
        summary=json.dumps({"patterns":len(patterns),"recommendations":len(recommendations),"calibration":calibration["status"]},sort_keys=True)
        self.db.cx.execute("UPDATE learning_runs SET completed_at=?,records_considered=?,status=?,summary=? WHERE id=?",
            (time.time(),considered,status,summary,run_id))
        return {"learning_run_id":run_id,"strategy_version":strategy,"patterns":[asdict(p) for p in patterns],
                "recommendations":recommendations,"calibration":calibration,"records_considered":considered,
                "status":status,"algorithm_version":ALGORITHM_VERSION,"feature_version":FEATURE_VERSION}

__all__=["LearningBrain","LearningStore","Pattern","ALGORITHM_VERSION"]
