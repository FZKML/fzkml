import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_governance import ROOT, digest, read_json, validate
from check_dco import check_message
from build_source import build


class GovernanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = copy.deepcopy(read_json(ROOT / "compliance/files.json"))
        self.paths = set(self.manifest["files"])
        for name in self.paths:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)

    def save(self, name, value):
        (self.root / name).write_text(json.dumps(value))

    def test_current_manifests(self):
        self.assertEqual(validate(self.root, self.paths)["assets"], 6)

    def test_controlled_missing_license_fixture(self):
        fixture = self.root / "unlicensed-example.py"
        fixture.write_text("# controlled missing-license fixture\n")
        with self.assertRaisesRegex(ValueError, "license coverage gap"):
            validate(self.root, self.paths | {fixture.name})

    def test_unknown_license(self):
        self.manifest["files"]["README.md"]["license"] = "UNKNOWN"
        self.save("compliance/files.json", self.manifest)
        with self.assertRaisesRegex(ValueError, "unreviewed license"):
            validate(self.root, self.paths)

    def test_changed_upstream_text(self):
        (self.root / "DCO").write_text("modified upstream text")
        with self.assertRaisesRegex(ValueError, "upstream checksum mismatch"):
            validate(self.root, self.paths)

    def test_asset_tampering(self):
        (self.root / "assets/public/governance-vector.json").write_text("tampered")
        with self.assertRaisesRegex(ValueError, "asset checksum"):
            validate(self.root, self.paths)

    def test_asset_required_field(self):
        assets = read_json(self.root / "assets/manifest.json")
        del assets["assets"][0]["terms"]
        self.save("assets/manifest.json", assets)
        with self.assertRaisesRegex(ValueError, "missing terms"):
            validate(self.root, self.paths)

    def test_restricted_redistribution(self):
        assets = read_json(self.root / "assets/manifest.json")
        assets["assets"][0]["permissions"]["release"] = "forbidden"
        self.save("assets/manifest.json", assets)
        with self.assertRaisesRegex(ValueError, "restricted/unapproved"):
            validate(self.root, self.paths)

    def test_unregistered_payload(self):
        name = "models/unreviewed.bin"
        path = self.root / name
        path.parent.mkdir()
        path.write_bytes(b"test")
        self.manifest["files"][name] = self.manifest["files"]["README.md"]
        self.save("compliance/files.json", self.manifest)
        with self.assertRaisesRegex(ValueError, "asset registry coverage gap"):
            validate(self.root, self.paths | {name})

    def test_new_dependency_manifest(self):
        name = "package.json"
        (self.root / name).write_text('{"dependencies":{"unknown":"*"}}')
        self.manifest["files"][name] = self.manifest["files"]["README.md"]
        self.save("compliance/files.json", self.manifest)
        with self.assertRaisesRegex(ValueError, "requires inventory integration"):
            validate(self.root, self.paths | {name})

    def test_dependency_lock_drift(self):
        with (self.root / "requirements-dev.txt").open("a") as handle:
            handle.write("unknown-package==1.0\n")
        with self.assertRaisesRegex(ValueError, "hash lock differs"):
            validate(self.root, self.paths)

    def test_ci_toolchain_inventory_drift(self):
        mutations = {
            "uv.lock": lambda text: text.replace('version = "4.25.1"', 'version = "99.0.0"'),
            "Cargo.lock": lambda text: text + '\n[[package]]\nname = "unknown-crate"\nversion = "1.0.0"\n',
            "tools-requirements.txt": lambda text: text.replace('--hash=sha256:', '--hash=sha256:0', 1),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                path = self.root / name
                original = path.read_text()
                path.write_text(mutate(original))
                with self.assertRaises(ValueError):
                    validate(self.root, self.paths)
                path.write_text(original)

    def test_private_or_escaped_paths(self):
        for name in ("../secret", "private/secret", "restricted/data"):
            with self.subTest(name=name):
                manifest = copy.deepcopy(self.manifest)
                manifest["files"][name] = manifest["files"]["README.md"]
                self.save("compliance/files.json", manifest)
                with self.assertRaisesRegex(ValueError, "unsafe path|excluded path"):
                    validate(self.root, self.paths | {name})

    def test_source_bundle_and_reproducible_bytes(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        # Temporary test repo has exactly the manifest files (no ignored build artifacts).
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        archive = build(self.root)
        first_hash = digest(archive)
        with tarfile.open(archive) as bundle:
            names = set(bundle.getnames())
            self.assertEqual(names, {"fzkml/" + p for p in self.paths})
            for required in ("LICENSE", "DCO", "compliance/third-party/cff-LICENSE"):
                self.assertIn("fzkml/" + required, names)
        self.assertEqual(first_hash, digest(build(self.root)))


class DCOTests(unittest.TestCase):
    author = "A Contributor <contributor@example.org>"

    def test_valid_trailer(self):
        check_message(self.author, "Change\n\nSigned-off-by: " + self.author + "\n")

    def test_missing_or_mismatched_trailer(self):
        for message in ("Change\n", "Change\n\nSigned-off-by: Someone Else <else@example.org>\n"):
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, "missing Signed-off-by"):
                    check_message(self.author, message)

    def test_body_text_is_not_trailer(self):
        with self.assertRaisesRegex(ValueError, "missing Signed-off-by"):
            check_message(self.author, "Change\n\nSigned-off-by: " + self.author + "\n\nFurther prose.\n")

    def test_coauthor_requires_own_signoff(self):
        message = "Change\n\nCo-authored-by: B Contributor <b@example.org>\nSigned-off-by: " + self.author + "\n"
        with self.assertRaisesRegex(ValueError, "missing Signed-off-by"):
            check_message(self.author, message)
        check_message(self.author, message + "Signed-off-by: B Contributor <b@example.org>\n")


if __name__ == "__main__":
    unittest.main()
