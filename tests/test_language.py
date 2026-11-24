from __future__ import annotations

import hashlib
import json
import unittest
from dataclasses import replace
from pathlib import Path
from typing import ClassVar

import torch
from fzkml_native import CanonicalBatch, ResearchSession, _native
from fzkml_native.torch_adapter import export_tensors, profile_tiny

from reference.numeric import decode, encode, evaluate, quantize

ROOT = Path(__file__).resolve().parents[1]


class NumericOracleTests(unittest.TestCase):
    def test_exact_ties_nonfinite_and_bounds(self) -> None:
        self.assertEqual(
            [quantize(v) for v in (0.03125, 0.09375, -0.03125, -0.09375)], [0, 2, 0, -2]
        )
        for value in (float("nan"), float("inf"), -float("inf"), 2.01, -2.01):
            with self.assertRaises(ValueError):
                quantize(value)

    def test_fixture_versions_hash_and_all_cases(self) -> None:
        fixture = json.loads((ROOT / "assets/public/numeric-v1.json").read_text())
        self.assertEqual(_native.CONTRACT_SHA256, fixture["contract_sha256"])
        self.assertEqual(
            fixture["contract_sha256"],
            hashlib.sha256((ROOT / "specs/numeric-contract-v1.json").read_bytes()).hexdigest(),
        )
        for vector in fixture["valid"]:
            data = bytes.fromhex(vector["canonical_hex"])
            self.assertEqual(evaluate(data), vector["expected"])
            self.assertEqual(CanonicalBatch(data).evaluate(), vector["expected"]["output"])
            self.assertEqual(encode(*decode(data)), data)
        for text in fixture["invalid_hex"]:
            with self.assertRaises(ValueError):
                CanonicalBatch(bytes.fromhex(text))

    def test_ffi_bounds_and_type_errors(self) -> None:
        for data in (b"", bytes(10_000_000)):
            with self.assertRaises(ValueError):
                _native.evaluate_batch(data)
        for value in (bytearray(84), [0] * 84, "0" * 84):
            with self.assertRaises(TypeError):
                _native.evaluate_batch(value)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            encode(True, [0] * 3, [0] * 3, [1] * 3)


class BindingProofTests(unittest.TestCase):
    session: ClassVar[ResearchSession]

    @classmethod
    def setUpClass(cls) -> None:
        cls.session = ResearchSession()

    def test_roundtrip_and_changed_public_output(self) -> None:
        batch = CanonicalBatch(encode(8, [16, -8, 24], [16, -16, 8], [1, 2, 1]))
        result = self.session.prove(batch)
        self.assertEqual(result.output, 9)
        self.assertTrue(self.session.verify(batch, result))
        self.assertFalse(self.session.verify(batch, replace(result, output=10)))
        self.assertFalse(self.session.verify(batch, replace(result, contract_version="other")))
        self.assertFalse(self.session.verify(batch, replace(result, key_id="other")))
        with self.assertRaises(ValueError):
            self.session.verify(batch, replace(result, proof=b""))
        with self.assertRaises(ValueError):
            self.session.verify(batch, replace(result, proof=bytes(10_000_000)))

    def test_other_canonical_roster_and_malformed_proof(self) -> None:
        batch = CanonicalBatch(encode(0, [0] * 3, [0] * 3, [1] * 3))
        result = self.session.prove(batch)
        changed = CanonicalBatch(encode(0, [0] * 3, [0] * 3, [2, 1, 1]))
        self.assertFalse(self.session.verify(changed, result))
        with self.assertRaises(ValueError):
            self.session.verify(batch, replace(result, proof=b"\xff" * 128))


class TorchAdapterTests(unittest.TestCase):
    def fixture(self) -> tuple[torch.nn.Linear, torch.Tensor, torch.Tensor]:
        model = torch.nn.Linear(1, 1, bias=False, dtype=torch.float64)
        with torch.no_grad():
            model.weight.fill_(0.5)
        return (
            model,
            torch.tensor([[1.0], [-0.5], [1.5]], dtype=torch.float64),
            torch.tensor([[1.0], [-1.0], [0.5]], dtype=torch.float64),
        )

    def test_exact_export_not_tolerance_comparison(self) -> None:
        model, x, y = self.fixture()
        batch, error = export_tensors(model, x, y, (1, 2, 1))
        self.assertEqual(batch.data, encode(8, [16, -8, 24], [16, -16, 8], [1, 2, 1]))
        self.assertEqual(error, 0)

    def test_unsupported_operator_shape_dtype_and_bad_values(self) -> None:
        model, x, y = self.fixture()
        hook = model.register_forward_hook(lambda module, args, output: output)
        with self.assertRaises(ValueError):
            export_tensors(model, x, y, (1, 2, 1))
        hook.remove()
        for unsupported in (
            torch.nn.ReLU(),
            torch.nn.Linear(1, 1, bias=True),
            torch.nn.Sequential(model),
        ):
            with self.assertRaises(ValueError):
                export_tensors(unsupported, x, y, (1, 2, 1))
        for bad_x in (
            x.float(),
            x.flatten(),
            torch.full_like(x, float("nan")),
            torch.full_like(x, float("inf")),
            torch.full_like(x, 2.01),
        ):
            with self.assertRaises(ValueError):
                export_tensors(model, bad_x, y, (1, 2, 1))

    def test_quality_profile_and_rng_settings_restore(self) -> None:
        model, x, y = self.fixture()
        state = torch.random.get_rng_state()
        deterministic = torch.are_deterministic_algorithms_enabled()
        result = profile_tiny(model, x, y, (1, 2, 1))
        self.assertTrue(result["proof_valid"])
        self.assertEqual(result["quality"]["integer_aggregate"], 9)
        self.assertEqual(result["quality"]["floating_aggregate"], 0.5546875)
        self.assertEqual(result["quality"]["absolute_training_difference"], 0.0078125)
        self.assertTrue(torch.equal(state, torch.random.get_rng_state()))
        self.assertEqual(deterministic, torch.are_deterministic_algorithms_enabled())
        self.assertEqual(
            set(result["seconds"]),
            {
                "training",
                "conversion_and_copying",
                "host_witness_generation",
                "proving",
                "setup",
                "verification",
            },
        )


def load_tests(
    loader: unittest.TestLoader, tests: unittest.TestSuite, pattern: str | None
) -> unittest.TestSuite:
    """Include S02's independent math cases in the existing Python language lane."""
    if pattern in (None, "test_language.py"):
        tests.addTests(loader.discover(str(ROOT / "tests"), pattern="test_s02_math.py"))
    return tests


if __name__ == "__main__":
    unittest.main()
