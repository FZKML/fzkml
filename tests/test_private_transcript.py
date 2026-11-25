from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path

from reference.private_transcript import (
    commitment,
    digest,
    leakage_example,
    public_vector,
    synthetic,
)

ROOT = Path(__file__).resolve().parents[1]


class PrivateTranscriptTests(unittest.TestCase):
    def test_public_vectors_and_exact_lengths(self) -> None:
        vector = public_vector()
        self.assertEqual(len(bytes.fromhex(str(vector["context_hex"]))), 316)
        self.assertEqual(len(bytes.fromhex(str(vector["statement_hex"]))), 396)
        saved = json.loads((ROOT / "assets/public/private-transcript-v1.json").read_text())
        self.assertEqual(saved["vector"], vector)

    def test_tiny_dictionary_and_public_blinding_leakage(self) -> None:
        result = leakage_example()
        self.assertEqual(result["deterministic_root_recovered"], [3])
        self.assertEqual(result["published_blinding_recovered"], [3])
        self.assertTrue(result["naive_concatenation_collision"])

    def test_every_context_field_is_distinct_or_rejected(self) -> None:
        context = synthetic()
        variants = [
            replace(context, session=bytes([8]) * 16),
            replace(context, round=2),
            replace(context, parent=digest(b"different-parent")),
            replace(
                context,
                roster=(context.roster[2], context.roster[1], context.roster[0]),
            ),
            replace(context, counts=(2, 2, 1)),
            replace(context, key_id=bytes([9]) * 32),
        ]
        for changed in variants:
            self.assertNotEqual(digest(context.encode()), digest(changed.encode()))
        for invalid in (
            replace(context, model_version=bytes(32)),
            replace(context, data_policy=bytes(32)),
            replace(context, optimizer=bytes(32)),
            replace(context, relation=bytes(32)),
            replace(context, contract=bytes(32)),
        ):
            with self.assertRaises(ValueError):
                invalid.encode()
        with self.assertRaises(ValueError):
            replace(context, roster=(context.roster[0],) * 3).encode()
        with self.assertRaises(ValueError):
            replace(context, round=0).encode()

    def test_domain_and_opening_substitution_changes_commitment(self) -> None:
        context = synthetic()
        root = commitment(
            b"FZKMOD01", bytes([11]) * 32, context, (8).to_bytes(8, "little", signed=True)
        )
        other = commitment(
            b"FZKMOD01", bytes([12]) * 32, context, (8).to_bytes(8, "little", signed=True)
        )
        self.assertNotEqual(root, other)
        with self.assertRaises(ValueError):
            commitment(b"FZKDAT01", bytes([11]) * 32, context, bytes(8))


if __name__ == "__main__":
    unittest.main()
