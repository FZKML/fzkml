"""Transactional synthetic event state plus an idempotent observer-ledger outbox.

SQLite and the existing observer journal are trusted local stores. This is not
consensus, malicious rollback resistance, a private publisher, or a DP mechanism.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from fractions import Fraction as F
from pathlib import Path
from typing import Any

from fzkml_transcript.ledger import LedgerPolicy, Observation, ReferenceAccountant, identifier

from .data_lineage import ORGS, Policy, Row, canonical, digest, partition, snapshot


class Stream:
    def __init__(self, path: Path, *, create: bool = False, expected_head: str | None = None):
        self.path = path
        if path.is_symlink() or (create and path.exists()) or (not create and not path.is_file()):
            raise ValueError("explicit-create-or-existing-trusted-database-required")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, isolation_level=None, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.ledger_policy = LedgerPolicy(
            "synthetic:stream-observer",
            "synthetic-record",
            digest("stream-ledger-policy", {"mode": "explicitly-unprotected", "release_slots": 4}),
            ORGS,
            F(0),
            F(0),
            (),
        )
        journal = path.with_suffix(".observer.jsonl")
        if create:
            self.db.executescript("""
            CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE events(id TEXT NOT NULL, version INTEGER NOT NULL, body TEXT NOT NULL,
                                digest TEXT NOT NULL, PRIMARY KEY(id,version));
            CREATE TABLE active(id TEXT PRIMARY KEY, version INTEGER NOT NULL,
                                body TEXT NOT NULL, tombstone INTEGER NOT NULL);
            CREATE TABLE snapshots(id TEXT PRIMARY KEY, round INTEGER UNIQUE NOT NULL,
                                   parent TEXT NOT NULL, manifest TEXT NOT NULL,
                                   payload TEXT NOT NULL);
            CREATE TABLE releases(id TEXT PRIMARY KEY,
                                  snapshot TEXT UNIQUE NOT NULL REFERENCES snapshots(id),
                                  body TEXT NOT NULL, observation TEXT NOT NULL, receipt TEXT,
                                  status TEXT NOT NULL CHECK(status IN ('reserved','accounted')));
            """)
            self.db.executemany(
                "INSERT INTO meta VALUES (?,?)",
                [
                    ("head", "genesis"),
                    ("round", "0"),
                    ("watermark", "-1"),
                    (
                        "policy",
                        digest(
                            "stream-policy",
                            {"unit": "cm", "version": 1, "source_roster": ORGS, "release_slots": 4},
                        ),
                    ),
                ],
            )
            self.ledger = ReferenceAccountant(journal, self.ledger_policy, create=True)
            self.db.execute(
                "INSERT INTO meta VALUES (?,?)", ("observer_root", self.ledger.summary()["root"])
            )
        else:
            expected_policy = digest(
                "stream-policy",
                {"unit": "cm", "version": 1, "source_roster": ORGS, "release_slots": 4},
            )
            if self.meta("policy") != expected_policy:
                raise ValueError("stream-policy-drift")
            self.ledger = ReferenceAccountant(
                journal, self.ledger_policy, expected_root=self.meta("observer_root")
            )
        self.validate_state()
        if expected_head is not None and self.meta("head") != expected_head:
            raise ValueError("stale-or-rolled-back-head")

    def validate_state(self) -> None:
        for row in self.db.execute("SELECT id,version,body,digest FROM events"):
            event = json.loads(row["body"])
            if (
                digest("versioned-event", event) != row["digest"]
                or event["id"] != row["id"]
                or event["version"] != row["version"]
            ):
                raise ValueError("persistent-event-lineage-integrity")
        for row in self.db.execute("SELECT id,version,body,tombstone FROM active"):
            event = self.db.execute(
                "SELECT body FROM events WHERE id=? AND version=?", (row["id"], row["version"])
            ).fetchone()
            if (
                event is None
                or json.loads(event[0])["row"] != json.loads(row["body"])
                or int(json.loads(event[0])["operation"] == "tombstone") != row["tombstone"]
            ):
                raise ValueError("active-state-does-not-match-event-lineage")

    def close(self) -> None:
        self.db.close()

    def meta(self, key: str) -> str:
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        if row is None:
            raise ValueError("missing-persistent-state")
        return str(row[0])

    def set_meta(self, key: str, value: str) -> None:
        self.db.execute("UPDATE meta SET value=? WHERE key=?", (value, key))

    def ingest(
        self,
        event: dict[str, Any],
        *,
        allow_closed_revision: bool = False,
        fault: Callable[[], None] | None = None,
        after_commit: Callable[[], None] | None = None,
    ) -> str:
        if set(event) != {"id", "version", "previous", "operation", "row", "arrival_time"}:
            raise ValueError("event-envelope-schema")
        if type(allow_closed_revision) is not bool:
            raise ValueError("boolean-correction-authority-action-required")
        row = Row(**event["row"])
        row.validate()
        if (
            event["id"] != row.id
            or type(event["version"]) is not int
            or not 1 <= event["version"] <= 8
        ):
            raise ValueError("event-identity-or-version")
        if type(event["arrival_time"]) is not int or not row.time <= event["arrival_time"] <= 2000:
            raise ValueError("arrival-time-or-units")
        if event["operation"] not in ("upsert", "tombstone"):
            raise ValueError("event-operation")
        value = digest("versioned-event", event)
        body = canonical(event).decode()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            old = self.db.execute(
                "SELECT digest FROM events WHERE id=? AND version=?",
                (event["id"], event["version"]),
            ).fetchone()
            if old is not None:
                if old[0] != value:
                    raise ValueError("changed-event-without-new-version")
                self.db.execute("COMMIT")
                return "identical-transport-retry-no-new-effect"
            if self.db.execute("SELECT count(*) FROM events").fetchone()[0] >= 256:
                raise ValueError("bounded-event-history")
            active = self.db.execute("SELECT * FROM active WHERE id=?", (event["id"],)).fetchone()
            if active is None:
                if self.db.execute("SELECT count(*) FROM active").fetchone()[0] >= 64:
                    raise ValueError("bounded-active-records")
                if (
                    event["version"] != 1
                    or event["previous"] is not None
                    or event["operation"] == "tombstone"
                ):
                    raise ValueError("missing-event-parent")
            else:
                parent = json.loads(active["body"])
                previous = self.db.execute(
                    "SELECT digest FROM events WHERE id=? AND version=?",
                    (event["id"], active["version"]),
                ).fetchone()[0]
                if event["version"] != active["version"] + 1 or event["previous"] != previous:
                    raise ValueError("out-of-order-event-lineage")
                if (parent["entity"], parent["org"]) != (row.entity, row.org):
                    raise ValueError("changed-source-or-entity")
                if active["tombstone"]:
                    raise ValueError("tombstone-is-terminal-in-this-reference")
                if event["operation"] == "tombstone" and event["row"] != parent:
                    raise ValueError("tombstone-must-bind-current-record")
            closed = row.time <= int(self.meta("watermark")) or (
                active is not None and parent["time"] <= int(self.meta("watermark"))
            )
            if closed and not allow_closed_revision:
                raise ValueError("closed-window-requires-explicit-correction-policy")
            self.db.execute(
                "INSERT INTO events VALUES (?,?,?,?)", (event["id"], event["version"], body, value)
            )
            self.db.execute(
                (
                    "INSERT INTO active VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE "
                    "SET version=excluded.version, body=excluded.body, "
                    "tombstone=excluded.tombstone"
                ),
                (
                    event["id"],
                    event["version"],
                    canonical(event["row"]).decode(),
                    int(event["operation"] == "tombstone"),
                ),
            )
            if fault is not None:
                fault()
            self.db.execute("COMMIT")
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise
        if after_commit is not None:
            after_commit()
        return value

    def advance(
        self, watermark: int, *, expected_parent: str, fault: Callable[[], None] | None = None
    ) -> dict[str, Any]:
        if type(watermark) is not int or not 0 <= watermark <= 1000:
            raise ValueError("watermark-domain")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            if self.db.execute("SELECT count(*) FROM releases WHERE status='reserved'").fetchone()[
                0
            ]:
                raise ValueError("recover-pending-disclosure-before-advancing")
            if int(self.meta("round")) >= 8:
                raise ValueError("bounded-accepted-rounds")
            if expected_parent != self.meta("head") or watermark < int(self.meta("watermark")):
                raise ValueError("stale-parent-or-watermark-rollback")
            self.validate_state()
            rows = tuple(
                Row(**json.loads(r[0]))
                for r in self.db.execute("SELECT body FROM active WHERE tombstone=0 ORDER BY id")
            )
            policy = Policy(cutoff=watermark)
            parts = tuple(
                partition(
                    tuple(r for r in rows if r.org == org), org, source_version="source-stream-1"
                )
                for org in ORGS
            )
            state = snapshot(parts, policy)
            active_versions = [
                list(r)
                for r in self.db.execute("SELECT id,version,tombstone FROM active ORDER BY id")
            ]
            manifest = {
                "event_time_window": [0, watermark],
                "parent": expected_parent,
                "round": int(self.meta("round")) + 1,
                "watermark": watermark,
                "source_snapshot": state["identity"],
                "active_versions": active_versions,
                "roster": list(ORGS),
                "policy": self.meta("policy"),
            }
            identity = digest("accepted-stream-state", manifest)
            payload = {
                "snapshot": identity,
                "parent": expected_parent,
                "round": manifest["round"],
                "count": state["manifest"]["selected_count"],
                "sum_mm": sum(r["value"] for r in state["rows"]),
                "disclosure": "exact-synthetic-output-explicitly-unprotected",
            }
            self.db.execute(
                "INSERT INTO snapshots VALUES (?,?,?,?,?)",
                (
                    identity,
                    manifest["round"],
                    expected_parent,
                    canonical(manifest).decode(),
                    canonical(payload).decode(),
                ),
            )
            self.set_meta("head", identity)
            self.set_meta("round", str(manifest["round"]))
            self.set_meta("watermark", str(watermark))
            if fault is not None:
                fault()
            self.db.execute("COMMIT")
            return payload
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise

    def reserve(
        self,
        release_id: str,
        snapshot_id: str,
        *,
        require_dp: bool = False,
        require_real_proof: bool = False,
    ) -> None:
        if require_dp or require_real_proof:
            raise ValueError("DP-or-proof-backend-unavailable")
        identifier(release_id)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            existing = self.db.execute(
                "SELECT snapshot FROM releases WHERE id=?", (release_id,)
            ).fetchone()
            if existing is not None:
                if existing[0] != snapshot_id:
                    raise ValueError("conflicting-release-id")
                self.db.execute("COMMIT")
                return
            if (
                self.db.execute(
                    "SELECT id FROM releases WHERE snapshot=?", (snapshot_id,)
                ).fetchone()
                is not None
            ):
                raise ValueError("snapshot-already-has-an-authorized-release-slot")
            if snapshot_id != self.meta("head"):
                raise ValueError("stale-snapshot-release")
            if self.db.execute("SELECT count(*) FROM releases").fetchone()[0] >= 4:
                raise ValueError("declared-release-slots-exhausted-not-DP-budget")
            row = self.db.execute(
                "SELECT payload FROM snapshots WHERE id=?", (snapshot_id,)
            ).fetchone()
            if row is None:
                raise ValueError("unknown-snapshot")
            payload = json.loads(row[0])
            observation = Observation(
                release_id,
                release_id,
                "aggregate",
                "explicitly-unprotected",
                digest("stream-public-payload", payload),
                "exact-public-synthetic-output-not-a-DP-mechanism",
            )
            self.db.execute(
                "INSERT INTO releases VALUES (?,?,?,?,?,?)",
                (
                    release_id,
                    snapshot_id,
                    row[0],
                    canonical(observation.record()).decode(),
                    None,
                    "reserved",
                ),
            )
            self.db.execute("COMMIT")
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise

    def recover_release(
        self, release_id: str, *, fault_after_journal: Callable[[], None] | None = None
    ) -> dict[str, Any]:
        row = self.db.execute("SELECT * FROM releases WHERE id=?", (release_id,)).fetchone()
        if row is None:
            raise ValueError("release-not-reserved")
        observation = json.loads(row["observation"])
        stored = self.db.execute(
            "SELECT payload FROM snapshots WHERE id=?", (row["snapshot"],)
        ).fetchone()
        if (
            stored is None
            or stored[0] != row["body"]
            or digest("stream-public-payload", json.loads(row["body"]))
            != observation["payload_digest"]
        ):
            raise ValueError("cached-release-payload-drift")
        observation["parents"] = tuple(observation["parents"])
        receipt = self.ledger.authorize(Observation(**observation))
        if fault_after_journal is not None:
            fault_after_journal()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute(
                "UPDATE releases SET status='accounted',receipt=? WHERE id=?", (receipt, release_id)
            )
            self.set_meta("observer_root", self.ledger.summary()["root"])
            self.db.execute("COMMIT")
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise
        # An identical cached output is re-delivered, with no fresh private access.
        return dict(json.loads(row["body"]))

    def status(self) -> dict[str, Any]:
        return {
            "head": self.meta("head"),
            "round": int(self.meta("round")),
            "watermark": int(self.meta("watermark")),
            "accepted_event_versions": self.db.execute("SELECT count(*) FROM events").fetchone()[0],
            "reserved_release_count": self.db.execute("SELECT count(*) FROM releases").fetchone()[
                0
            ],
            "accounted_release_count": self.db.execute(
                "SELECT count(*) FROM releases WHERE status='accounted'"
            ).fetchone()[0],
            "roster": list(ORGS),
            "observer_ledger": self.ledger.summary(),
            "trust": "local SQLite/journal/clock/authority; no malicious joint rollback resistance",
        }
