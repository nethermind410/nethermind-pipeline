import inspect

from clipping_farm.adaptive_brain import AdaptiveBrain
from clipping_farm.candidates import Candidate
from clipping_farm.evidence import EvidencePacket, build_packet


def test_candidate_builds_valid_evidence_packet():
    candidate = Candidate(
        start=10.0,
        end=20.0,
        text="A complete candidate.",
        scores={"standalone": 8.0},
        decision="ACCEPT",
    )

    packet = build_packet(
        candidate,
        transcript=[
            {"start": 0.0, "end": 10.0, "text": "Before."},
            {"start": 10.0, "end": 20.0, "text": "A complete candidate."},
            {"start": 20.0, "end": 30.0, "text": "After."},
        ],
        audio={},
        scenes=[],
        frames=[],
        metadata={},
    )

    assert isinstance(packet, EvidencePacket)
    assert packet.candidate["start"] == 10.0
    assert packet.candidate["end"] == 20.0
    assert packet.candidate["text"] == "A complete candidate."

    # The object passed to AdaptiveBrain must satisfy its real contract.
    sig = inspect.signature(AdaptiveBrain.analyse)
    assert "packet" in sig.parameters
    assert hasattr(packet, "to_dict")


def test_adaptive_brain_accepts_evidence_packet_contract():
    sig = inspect.signature(AdaptiveBrain.analyse)

    assert list(sig.parameters)[1] == "packet"
    assert sig.parameters["packet"].annotation is not inspect.Parameter.empty
