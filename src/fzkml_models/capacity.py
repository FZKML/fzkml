"""Exact workload arithmetic, bounded queue simulation and public SQLite recovery.

The queue is simulated; the ledger exercises local persistence, not consensus,
secure aggregation or an external exactly-once delivery guarantee.
"""

from __future__ import annotations

import heapq
import sqlite3
from dataclasses import dataclass
from fractions import Fraction as Q
from pathlib import Path

from .algebra import digest, ensure


@dataclass(frozen=True)
class Workload:
    enrolled: int
    selected: int
    coordinates: int
    coordinate_bits: int
    buckets: int
    proof_envelope_bytes: int
    verifier_seconds: Q
    workers: int
    window_seconds: Q
    ingress_bits_per_second: int
    accumulator_bits: int
    replicas: int = 1
    records_per_client: int = 1
    proof_trace_steps: int = 1
    weighted_coordinate_bound: int | None = None

    def metrics(self) -> dict[str, int | Q | bool]:
        integers = [
            self.enrolled,
            self.selected,
            self.coordinates,
            self.coordinate_bits,
            self.buckets,
            self.proof_envelope_bytes,
            self.workers,
            self.ingress_bits_per_second,
            self.accumulator_bits,
            self.replicas,
            self.records_per_client,
            self.proof_trace_steps,
        ]
        ensure(all(type(v) is int and 0 < v <= 10**12 for v in integers), "workload-bounds")
        ensure(
            self.selected <= self.enrolled
            and self.buckets <= self.selected
            and self.coordinate_bits in {8, 16, 32, 64}
            and self.accumulator_bits in {8, 16, 32, 64, 128}
            and self.verifier_seconds > 0
            and self.window_seconds > 0,
            "workload-policy",
        )
        payload = self.selected * self.coordinates * self.coordinate_bits // 8
        required = (
            None
            if self.weighted_coordinate_bound is None
            else (self.selected * self.weighted_coordinate_bound)
        )
        if required is not None:
            ensure(
                self.weighted_coordinate_bound is not None and self.weighted_coordinate_bound >= 0,
                "coordinate-hard-bound",
            )
            ensure(required <= 2 ** (self.accumulator_bits - 1) - 1, "accumulator-overflow")
        return {
            "enrolled": self.enrolled,
            "selected": self.selected,
            "records": self.selected * self.records_per_client,
            "coordinates": self.coordinates,
            "proof_trace_steps": self.proof_trace_steps,
            "update_bytes": self.coordinates * self.coordinate_bits // 8,
            "client_upload_bytes": payload,
            "replicated_upload_bytes": payload * self.replicas,
            "conditional_partial_bytes": self.buckets
            * self.coordinates
            * self.accumulator_bits
            // 8,
            "accumulator_range_certified": required is not None,
            "proof_traffic_bytes": self.selected * self.proof_envelope_bytes,
            "verification_cpu_seconds": self.selected * self.verifier_seconds,
            "ideal_verification_seconds": self.selected * self.verifier_seconds / self.workers,
            "ideal_ingress_seconds": Q(payload * 8, self.ingress_bits_per_second),
            "arrival_per_second": self.selected / self.window_seconds,
            "utilization": self.selected
            * self.verifier_seconds
            / (self.window_seconds * self.workers),
            "accumulator_bits": self.accumulator_bits,
            "replicas": self.replicas,
        }


@dataclass(frozen=True)
class Job:
    client: str
    arrival: Q
    service: Q
    deadline: Q
    dropout: bool = False
    valid: bool = True


def simulate(
    jobs: tuple[Job, ...], worker_speeds: tuple[Q, ...], queue_limit: int = 256
) -> list[dict[str, str | Q | None]]:
    ensure(0 < len(jobs) <= 256 and 0 < len(worker_speeds) <= 64, "simulation-budget")
    ensure(all(type(s) is Q and 0 < s <= 16 for s in worker_speeds), "worker-speeds")
    ensure(0 <= queue_limit <= 256 and len({j.client for j in jobs}) == len(jobs), "queue-policy")
    workers = [(Q(0), index) for index in range(len(worker_speeds))]
    heapq.heapify(workers)
    waiting_finish: list[Q] = []
    results: list[dict[str, str | Q | None]] = []
    for job in sorted(jobs, key=lambda j: (j.arrival, j.client)):
        ensure(job.arrival >= 0 and job.service > 0 and job.deadline >= job.arrival, "job-time")
        waiting_finish = [end for end in waiting_finish if end > job.arrival]
        if job.dropout:
            results.append(
                {"client": job.client, "status": "dropout", "latency": None, "queue_wait": None}
            )
            continue
        available, worker = heapq.heappop(workers)
        if available > job.arrival and len(waiting_finish) >= queue_limit:
            heapq.heappush(workers, (available, worker))
            results.append(
                {"client": job.client, "status": "overload", "latency": None, "queue_wait": None}
            )
            continue
        start = max(available, job.arrival)
        end = start + job.service / worker_speeds[worker]
        heapq.heappush(workers, (end, worker))
        if start > job.arrival:
            waiting_finish.append(start)
        # Late/invalid jobs still consumed verifier resources. Deadline censoring
        # is retained explicitly rather than removed from the population.
        status = "deadline" if end > job.deadline else "accepted" if job.valid else "invalid"
        results.append(
            {
                "client": job.client,
                "status": status,
                "latency": end - job.arrival,
                "queue_wait": start - job.arrival,
            }
        )
    return results


class ReleaseLedger:
    """One local authority, public synthetic payloads, atomic output record."""

    def __init__(self, path: Path, session: str, roster: tuple[str, ...], context: str):
        ensure(0 < len(roster) <= 256 and len(set(roster)) == len(roster), "accepted-roster")
        ensure(
            bool(session)
            and len(session) <= 100
            and bool(context)
            and len(context) <= 1000
            and all(isinstance(c, str) and 0 < len(c) <= 100 for c in roster),
            "ledger-identities",
        )
        self.db = sqlite3.connect(path, timeout=5, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS policy (session TEXT PRIMARY KEY, context TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS payload (
              session TEXT NOT NULL, client TEXT NOT NULL, value INTEGER NOT NULL,
              PRIMARY KEY(session,client));
            CREATE TABLE IF NOT EXISTS output (
              session TEXT PRIMARY KEY, receipt TEXT NOT NULL, value INTEGER NOT NULL);
        """)
        self.session, self.roster = session, tuple(sorted(roster))
        self.context = digest({"roster": self.roster, "context": context})
        self.db.execute("INSERT OR IGNORE INTO policy VALUES (?,?)", (session, self.context))
        if self.db.execute("SELECT context FROM policy WHERE session=?", (session,)).fetchone() != (
            self.context,
        ):
            self.db.close()
            raise ValueError("restart-context-or-roster-drift")

    def close(self) -> None:
        self.db.close()

    def submit(self, client: str, value: int) -> None:
        ensure(
            client in self.roster and type(value) is int and abs(value) <= 1_000_000,
            "unauthorized-or-oversized-payload",
        )
        self.db.execute("BEGIN IMMEDIATE")
        try:
            previous = self.db.execute(
                "SELECT value FROM payload WHERE session=? AND client=?", (self.session, client)
            ).fetchone()
            ensure(previous is None or previous == (value,), "conflicting-retry")
            if previous is None:
                ensure(
                    self.db.execute(
                        "SELECT 1 FROM output WHERE session=?", (self.session,)
                    ).fetchone()
                    is None,
                    "release-already-finalized",
                )
                self.db.execute("INSERT INTO payload VALUES (?,?,?)", (self.session, client, value))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def finalize(self, interrupt_before_commit: bool = False) -> tuple[str, int]:
        self.db.execute("BEGIN IMMEDIATE")
        try:
            previous = self.db.execute(
                "SELECT receipt,value FROM output WHERE session=?", (self.session,)
            ).fetchone()
            if previous is not None:
                result = (str(previous[0]), int(previous[1]))
            else:
                rows = self.db.execute(
                    "SELECT client,value FROM payload WHERE session=? ORDER BY client",
                    (self.session,),
                ).fetchall()
                ensure(tuple(r[0] for r in rows) == self.roster, "accepted-payload-unavailable")
                value = sum(int(row[1]) for row in rows)
                result = (
                    digest(
                        {
                            "session": self.session,
                            "context": self.context,
                            "rows": rows,
                            "value": value,
                        }
                    ),
                    value,
                )
                self.db.execute("INSERT INTO output VALUES (?,?,?)", (self.session, *result))
            if interrupt_before_commit:
                raise RuntimeError("synthetic-crash-before-commit")
            self.db.execute("COMMIT")
            return result
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
