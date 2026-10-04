"""Offline providers used to exercise escalation without paid APIs."""
from .providers import BrainProvider, ProviderResult


class CheapMockProvider(BrainProvider):
    name = "cheap-mock"
    modality = "multimodal"

    def analyse(self, packet):
        standalone = float(packet.candidate.get("scores", {}).get("standalone", 0))
        confidence = 0.88 if standalone >= 0.65 else 0.73
        decision = "accept" if confidence >= 0.80 and standalone >= 0.65 else "reject"
        return ProviderResult(
            decision=decision,
            confidence=confidence,
            reason="cheap mock evidence classification",
            evidence=["compact evidence packet inspected"],
            scores=dict(packet.candidate.get("scores", {})),
            model=self.name,
            estimated_cost=0.005,
            actual_cost=0.005,
        )


class PremiumMockProvider(BrainProvider):
    name = "premium-mock"
    modality = "multimodal"

    def analyse(self, packet):
        standalone = float(packet.candidate.get("scores", {}).get("standalone", 0))
        decision = "accept" if standalone >= 0.60 else "reject"
        return ProviderResult(
            decision=decision,
            confidence=0.96,
            reason="premium mock final editorial review",
            evidence=["compact evidence packet inspected at premium tier"],
            scores=dict(packet.candidate.get("scores", {})),
            model=self.name,
            estimated_cost=0.05,
            actual_cost=0.05,
        )
