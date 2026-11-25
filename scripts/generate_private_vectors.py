"""Original public transcript and leakage fixtures from independent Python code."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reference.private_transcript import leakage_example, public_vector  # noqa: E402

result = {
    "vector": public_vector(),
    "leakage": leakage_example(),
    "generator": "reference/private_transcript.py; Python stdlib SHA-256 and struct",
    "private_source_inputs": "none; all values and openings in this fixture are public",
}
(ROOT / "assets/public/private-transcript-v1.json").write_text(json.dumps(result, indent=2) + "\n")
print("Generated original private-transcript-v1 public fixture")
