"""Bounded QC repair loop."""
def repair_candidate(candidate, qc_fn, *, max_repairs=2, extend=4.0):
    attempts=0
    while attempts < max_repairs:
        qc=qc_fn(candidate)
        if qc.passed: return candidate, qc, attempts
        if not qc.repairable: return candidate, qc, attempts
        attempts += 1
        if "extend_start_or_end" in qc.repairs:
            candidate.start=max(0.0,candidate.start-extend)
            candidate.end += extend
    qc=qc_fn(candidate)
    return candidate,qc,attempts
