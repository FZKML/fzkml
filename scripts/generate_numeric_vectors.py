"""Generate original public vectors using only the independent Fraction oracle."""

import hashlib
import json
import random
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reference.numeric import CONTRACT_VERSION, FIXTURE_VERSION, encode, evaluate  # noqa: E402

rng = random.Random(20261124)
batches = [
    (0, [0, 0, 0], [0, 0, 0], [1, 1, 1]),
    (1, [0, 0, 0], [0, 0, 0], [1, 1, 1]),
    (8, [16, -8, 24], [16, -16, 8], [1, 2, 1]),
    (-32, [-32, 32, -32], [32, -32, -32], [4, 4, 4]),
    (32, [32, -32, 32], [-32, 32, 32], [1, 4, 1]),
]
for _ in range(256):
    batches.append(
        (
            rng.randint(-32, 32),
            [rng.randint(-32, 32) for _ in range(3)],
            [rng.randint(-32, 32) for _ in range(3)],
            [rng.randint(1, 4) for _ in range(3)],
        )
    )
valid = []
for args in batches:
    data = encode(*args)
    valid.append({"canonical_hex": data.hex(), "expected": evaluate(data)})
zero = encode(*batches[0])
invalid = [
    b"",
    zero[:-1],
    zero + b"\0",
    b"WRONG001" + zero[8:],
    zero[:8] + struct.pack("<HHI", 2, 3, 16) + zero[16:],
    zero[:16] + struct.pack("<q", 33) + zero[24:],
    zero[:16] + struct.pack("<q", -33) + zero[24:],
    zero[:16] + struct.pack("<q", -(1 << 63)) + zero[24:],
    zero[:40] + struct.pack("<I", 0) + zero[44:],
    zero[:40] + struct.pack("<I", 5) + zero[44:],
    zero[:40] + struct.pack("<I", (1 << 32) - 1) + zero[44:],
]
document = {
    "contract_version": CONTRACT_VERSION,
    "fixture_version": FIXTURE_VERSION,
    "contract_sha256": hashlib.sha256(
        (ROOT / "specs/numeric-contract-v1.json").read_bytes()
    ).hexdigest(),
    "oracle": "Python standard-library fractions.Fraction; no Rust bindings",
    "seed": 20261124,
    "valid": valid,
    "invalid_hex": [v.hex() for v in invalid],
}
path = ROOT / "assets/public/numeric-v1.json"
path.write_text(json.dumps(document, indent=2) + "\n")
print(path.name, hashlib.sha256(path.read_bytes()).hexdigest())
