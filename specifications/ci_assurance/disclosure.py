"""Known-canary regression scanning is not a semantic confidentiality proof."""

from __future__ import annotations

import base64
import re
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote_from_bytes

from specifications.ci_assurance.rounds import require

CHANNELS = {"logs", "public-inputs", "metrics", "uploads", "recovery"}


def scan_views(root: Path, inventory: list[dict[str, Any]], canary: bytes) -> dict[str, int]:
    require(root.is_dir() and not root.is_symlink() and 16 <= len(canary) <= 128, "scan-policy")
    require(
        1 <= len(inventory) <= 32 and {e["channel"] for e in inventory} == CHANNELS,
        "missing-release-view",
    )
    declared = {e["path"] for e in inventory}
    require(len(declared) == len(inventory), "duplicate-export-path")
    for entry in inventory:
        parts = PurePosixPath(entry["path"]).parts
        require(
            entry["visibility"] == "public"
            and entry["role"] in {"public", "coordinator"}
            and bool(re.fullmatch(r"[A-Za-z0-9_./-]{1,128}", entry["path"]))
            and parts
            and not entry["path"].startswith("/")
            and not any(p.startswith(".") for p in parts),
            "unsafe-view-inventory",
        )
    found: set[str] = set()
    visited = total = 0
    markers = {
        canary,
        canary.hex().encode(),
        canary.hex().upper().encode(),
        base64.b64encode(canary),
        quote_from_bytes(canary, safe="").encode(),
    }
    for path in root.rglob("*"):
        visited += 1
        require(visited <= 64 and not path.is_symlink(), "scan-resource-or-symlink")
        if not path.is_file():
            continue
        name = path.relative_to(root).as_posix()
        require(name in declared, "unlisted-public-export")
        size = path.stat().st_size
        total += size
        require(size <= 1048576 and total <= 4194304, "scan-byte-budget")
        payload = path.read_bytes()
        # Do not include path, offending bytes or canary in any diagnostic.
        require(not any(marker in payload for marker in markers), "prohibited-canary-disclosure")
        found.add(name)
    require(found == declared, "missing-declared-export")
    return {"files_scanned": len(found), "bytes_scanned": total}
