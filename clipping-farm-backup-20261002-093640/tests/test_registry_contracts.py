import unittest

from clipping_farm.model_registry import ModelRegistry
from clipping_farm.provider_contracts import validate_packet, validate_result


class RegistryContractTests(unittest.TestCase):
    def test_registry_selects_cheapest_qualified_tier(self):
        registry = ModelRegistry()
        spec = registry.choose(
            "brain.reasoning", tier="cheap",
            quality_required=.70, budget=.01, modality="multimodal",
        )
        self.assertEqual(spec.name, "cheap-mock")

    def test_registry_respects_budget(self):
        registry = ModelRegistry()
        spec = registry.choose(
            "brain.reasoning", tier="premium",
            quality_required=.90, budget=.01, modality="multimodal",
        )
        self.assertIsNone(spec)

    def test_invalid_provider_result_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_result({
                "decision": "accept", "confidence": 1.5, "reason": "",
                "evidence": [], "scores": {}, "model": "x",
            })

    def test_packet_contract_is_explicit(self):
        packet = {
            "candidate": {}, "transcript": [], "context_before": "",
            "context_after": "", "audio": {}, "scenes": [], "frames": [],
            "source_metadata": {},
        }
        validate_packet(packet)


if __name__ == "__main__":
    unittest.main()
