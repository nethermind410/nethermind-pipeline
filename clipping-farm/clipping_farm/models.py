from dataclasses import dataclass, field
from typing import Any, Optional

JOB_STATES = {"PENDING","READY","CLAIMED","RUNNING","COMPLETE","FAILED","TIMEOUT","CANCELLED","RETRYING","DEAD_LETTER"}
RIGHTS_STATES = {"UNKNOWN","PENDING","AUTHORISED","REJECTED","EXPIRED"}
APPROVAL_STATES = {"NOT_REQUIRED","READY_FOR_REVIEW","APPROVED","REJECTED"}

@dataclass
class AgentRequest:
    job_id: str
    parent_job_id: Optional[str]
    agent: str
    task: str
    input: dict[str, Any]
    constraints: dict[str, Any] = field(default_factory=dict)
    quality_required: float = 0.0
    budget_remaining: float = 0.0
    deadline: Optional[str] = None
    context_refs: list[str] = field(default_factory=list)

@dataclass
class AgentResult:
    job_id: str
    agent: str
    status: str
    decision: Optional[str] = None
    confidence: float = 0.0
    reason: str = ""
    evidence: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    model: Optional[str] = None
    estimated_cost: float = 0.0
    actual_cost: float = 0.0
    duration_ms: int = 0
    retryable: bool = False
    error: Optional[str] = None
