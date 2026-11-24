"""Verify the native wheel contains its actual transitive license/notice bundle."""

import hashlib
import json
import sys
from pathlib import Path
from zipfile import ZipFile

path = Path(sys.argv[1])
with ZipFile(path) as wheel:
    root = "fzkml_native/licenses/"
    files = set(wheel.namelist())
    assert not any(name.startswith("/") or ".." in name.split("/") for name in files)
    assert root + "LICENSE" in files
    assert root + "rust-standard-library/COPYRIGHT" in files
    repository = Path(__file__).resolve().parents[1]
    for name in ("COPYRIGHT", "LICENSE-APACHE", "LICENSE-MIT"):
        assert (
            wheel.read(root + "rust-standard-library/" + name)
            == (
                repository / "bindings/python/fzkml_native/licenses/rust-standard-library" / name
            ).read_bytes()
        )
    assert "fzkml_native/py.typed" in files
    inventory = json.loads(wheel.read(root + "rust-dependencies.json"))
    for dependency in inventory["dependencies"]:
        for notice in dependency["license_files"]:
            name = root + notice["path"]
            assert name in files, "missing native dependency notice"
            assert hashlib.sha256(wheel.read(name)).hexdigest() == notice["sha256"]
    assert not any(
        "private" in name.split("/") or "restricted" in name.split("/") for name in files
    )
print("Native wheel license/notice bundle and typing metadata verified:", path.name)
