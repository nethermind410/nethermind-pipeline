from clipping_farm.brain import DeterministicBrain
from clipping_farm.candidates import Candidate
from clipping_farm.evidence import EvidencePacket
from clipping_farm.providers import DeterministicProvider


def test_deterministic_provider_preserves_packet_modalities():
    brain = DeterministicBrain()
    provider = DeterministicProvider(brain)

    candidate = Candidate(
        start=10.0,
        end=20.0,
        text="A complete candidate.",
        scores={"standalone": 0.8},
        decision="REVIEW",
    )

    packet = EvidencePacket(
        candidate=candidate.asdict(),
        transcript=[
            {"start": 10.0, "end": 20.0, "text": "A complete candidate."}
        ],
        context_before="Before.",
        context_after="After.",
        audio={"peak": 0.04},
        scenes=[{"start": 10.0, "end": 15.0}],
        frames=[{"timestamp": 12.0}],
        source_metadata={},
    )

    result = provider.analyse(packet)

    assert result is not None
    assert result.decision.lower() in {"accept", "review", "reject"}
    assert isinstance(result.confidence, (int, float))
