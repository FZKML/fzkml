"""Build three deliberately broken Rust variants and require conformance failure."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
work = ROOT / ".mutation-work"
work.mkdir(exist_ok=True)
for name in ("Cargo.toml", "Cargo.lock"):
    shutil.copyfile(ROOT / name, work / name)
shutil.copytree(ROOT / "crates", work / "crates", dirs_exist_ok=True)
shutil.copytree(ROOT / "specs", work / "specs", dirs_exist_ok=True)
path = work / "crates/fzkml-core/src/lib.rs"
original = path.read_text()
mutations = {
    "rounding": ("2 * r > d || (2 * r == d && q.rem_euclid(2) == 1)", "2 * r >= d"),
    "endianness": ("i64::from_le_bytes", "i64::from_be_bytes"),
    "range": ("!(-32..=32).contains(v)", "!(-33..=33).contains(v)"),
}
results = []
try:
    for name, (old, new) in mutations.items():
        if original.count(old) != 1:
            raise ValueError("mutation anchor drift: " + name)
        path.write_text(original.replace(old, new))
        subprocess.run(
            [
                "cargo",
                "build",
                "--release",
                "--offline",
                "--locked",
                "-p",
                "fzkml-core",
                "--bin",
                "fzkml-contract",
                "--manifest-path",
                str(work / "Cargo.toml"),
                "--target-dir",
                str(ROOT / "target/mutants"),
            ],
            check=True,
        )
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/conformance.py"),
                str(ROOT / "target/mutants/release/fzkml-contract"),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 1:
            raise AssertionError("conformance did not reject " + name)
        results.append(
            {"mutation": name, "detected": True, "counterexample": json.loads(result.stderr)}
        )
finally:
    path.write_text(original)
    # Mutants use a separate output tree and cannot overwrite the real CLI/wheel.
(ROOT / "reports").mkdir(exist_ok=True)
(ROOT / "reports/mutation-conformance.json").write_text(json.dumps(results, indent=2) + "\n")
print(json.dumps(results, sort_keys=True))
