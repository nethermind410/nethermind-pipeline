"""Small, provider-neutral contracts for Brain requests and responses."""
from typing import Any, Dict

REQUIRED_PACKET_FIELDS = (
    "candidate", "transcript", "context_before", "context_after",
    "audio", "scenes", "frames", "source_metadata",
)
REQUIRED_RESULT_FIELDS = (
    "decision", "confidence", "reason", "evidence", "scores", "model",
)

def validate_packet(packet: Dict[str, Any]) -> None:
    missing = [key for key in REQUIRED_PACKET_FIELDS if key not in packet]
    if missing:
        raise ValueError("EvidencePacket missing fields: " + ", ".join(missing))

def validate_result(result: Dict[str, Any]) -> None:
    missing = [key for key in REQUIRED_RESULT_FIELDS if key not in result]
    if missing:
        raise ValueError("ProviderResult missing fields: " + ", ".join(missing))
    confidence = float(result["confidence"])
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("Provider confidence must be between 0 and 1")
    if result["decision"] not in {"accept", "reject", "review"}:
        raise ValueError("Unsupported provider decision")

PROMPT_CONTRACTS = {
    "brain.reasoning": {
        "system": "Judge the candidate using only supplied evidence. Do not invent missing context. Return structured JSON.",
        "input": "EvidencePacket",
        "output": "ProviderResult",
        "max_context_policy": "compact-evidence-only",
    },
    "brain.qc": {
        "system": "Perform final editorial QC from supplied evidence. Identify concrete failures and repairable defects.",
        "input": "EvidencePacket",
        "output": "ProviderResult",
        "max_context_policy": "compact-evidence-only",
    },
}
