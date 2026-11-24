"""Exclusive cost events, concurrent live-resource samples, and censored quality time."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from fractions import Fraction
from typing import Any, Literal

from fzkml_ci.validate import require

PHASES = {
    "prepare",
    "train",
    "witness",
    "prove",
    "transfer",
    "aggregate",
    "verify",
    "setup",
    "evaluate",
    "release",
}


@dataclass(frozen=True)
class Event:
    cost_id: str
    attempt_id: str
    worker: str
    phase: str
    start_ns: int
    end_ns: int
    cpu_ns: int
    bytes_sent: int = 0
    status: Literal["successful", "failed", "inconclusive"] = "successful"
    setup_mode: Literal["cold", "warm", "not-applicable"] = "not-applicable"
    reuse_cost_ids: tuple[str, ...] = ()
    contribution_id: str = "synthetic:one"


@dataclass(frozen=True)
class LiveSample:
    time_ns: int
    worker: str
    ram_bytes: int
    disk_bytes: int
    vram_bytes: int | None = None


@dataclass(frozen=True)
class QualityEvent:
    time_ns: int
    quality: Fraction
    certificate_verified: bool
    release_authorized: bool


def summarize(
    events: list[Event],
    samples: list[LiveSample],
    quality: list[QualityEvent],
    *,
    budget_ns: int,
    quality_target: Fraction,
) -> dict[str, Any]:
    require(
        bool(events) and len(events) <= 10_000 and type(budget_ns) is int and budget_ns > 0,
        "profile-domain",
    )
    require(len(samples) <= 50_000 and len(quality) <= 10_000, "profile-size")
    ids = {e.cost_id: e for e in events}
    require(len(ids) == len(events), "duplicate-cost-id")
    lanes: dict[str, list[Event]] = defaultdict(list)
    for event in events:
        require(
            all((event.cost_id, event.attempt_id, event.worker)) and event.phase in PHASES,
            "profile-event-identity",
        )
        require(
            all(
                type(v) is int and v >= 0
                for v in (event.start_ns, event.end_ns, event.cpu_ns, event.bytes_sent)
            ),
            "profile-cost-domain",
        )
        require(
            event.start_ns <= event.end_ns <= budget_ns and event.cpu_ns <= budget_ns * 128,
            "profile-time-range",
        )
        require(event.status in {"successful", "failed", "inconclusive"}, "profile-status")
        require(
            (event.phase == "setup" and event.setup_mode in {"cold", "warm"})
            or (event.phase != "setup" and event.setup_mode == "not-applicable"),
            "setup-mode-required",
        )
        require(
            len(set(event.reuse_cost_ids)) == len(event.reuse_cost_ids), "duplicate-reuse-reference"
        )
        for ref in event.reuse_cost_ids:
            require(
                ref in ids and ids[ref].phase == "setup" and ids[ref].end_ns <= event.start_ns,
                "invalid-setup-reuse",
            )
        lanes[event.worker].append(event)
    for lane in lanes.values():
        ordered = sorted(lane, key=lambda e: (e.start_ns, e.end_ns))
        require(
            all(a.end_ns <= b.start_ns for a, b in zip(ordered, ordered[1:], strict=False)),
            "inclusive-or-overlapping-worker-costs",
        )
    live: dict[str, LiveSample] = {}
    peaks: dict[str, int | None] = {"ram_bytes": 0, "disk_bytes": 0, "vram_bytes": 0}
    updates: dict[int, list[LiveSample]] = defaultdict(list)
    for sample in samples:
        require(
            sample.worker in lanes
            and type(sample.time_ns) is int
            and 0 <= sample.time_ns <= budget_ns,
            "resource-sample-scope",
        )
        require(
            all(type(v) is int and v >= 0 for v in (sample.ram_bytes, sample.disk_bytes)),
            "resource-sample-domain",
        )
        require(
            sample.vram_bytes is None or type(sample.vram_bytes) is int and sample.vram_bytes >= 0,
            "vram-sample-domain",
        )
        updates[sample.time_ns].append(sample)
    for time in sorted(updates):
        require(
            len({s.worker for s in updates[time]}) == len(updates[time]),
            "duplicate-resource-sample",
        )
        live.update({s.worker: s for s in updates[time]})
        for field in peaks:
            values = [getattr(s, field) for s in live.values()]
            if any(v is None for v in values):
                peaks[field] = None
            elif peaks[field] is not None:
                peaks[field] = max(peaks[field], sum(values))
    qualified = []
    for entry in quality:
        require(
            type(entry.certificate_verified) is bool
            and type(entry.release_authorized) is bool
            and isinstance(entry.quality, Fraction),
            "quality-evidence-domain",
        )
        require(
            type(entry.time_ns) is int and 0 <= entry.time_ns <= budget_ns, "quality-time-domain"
        )
        if (
            entry.quality <= quality_target
            and entry.certificate_verified
            and entry.release_authorized
        ):
            require(
                any(
                    e.phase == "release" and e.status == "successful" and e.end_ns == entry.time_ns
                    for e in events
                ),
                "quality-without-authorized-release",
            )
            qualified.append(entry.time_ns)
    attempts: dict[str, set[str]] = defaultdict(set)
    for event in events:
        if event.phase != "setup":
            require(bool(event.contribution_id), "contribution-id-required")
            attempts[event.contribution_id].add(event.attempt_id)
    if not samples:
        peaks = {key: None for key in peaks}
    first = min(e.start_ns for e in events)
    last = max(e.end_ns for e in events)
    return {
        "wall_ns": last - first,
        "aggregate_worker_occupied_ns": sum(e.end_ns - e.start_ns for e in events),
        "aggregate_cpu_ns": sum(e.cpu_ns for e in events),
        "bytes_sent": sum(e.bytes_sent for e in events),
        "attempts": sum(map(len, attempts.values())),
        "retries": sum(max(0, len(group) - 1) for group in attempts.values()),
        "failed_cost_ids": sorted(e.cost_id for e in events if e.status == "failed"),
        "setup_cold_ns": sum(e.end_ns - e.start_ns for e in events if e.setup_mode == "cold"),
        "setup_warm_ns": sum(e.end_ns - e.start_ns for e in events if e.setup_mode == "warm"),
        "sampled_joint_live_peaks": peaks,
        "time_to_certified_quality": {
            "status": "observed" if qualified else "right-censored",
            "time_ns": min(qualified) - first if qualified else None,
            "budget_ns": budget_ns,
        },
        "limitations": [
            "Sampled live peaks are lower bounds unless every resource change is observed.",
            "Sum worker occupancy is work, not end-to-end latency.",
            "CPU work must come from exclusive per-worker counters.",
            "Retries are counted per contribution; shared setup costs occur once.",
        ],
    }


def ledger(events: list[Event], samples: list[LiveSample]) -> dict[str, Any]:
    return {
        "companion_version": "profile-ledger-1.0.0",
        "events": list(map(asdict, events)),
        "resource_samples": list(map(asdict, samples)),
    }


def amdahl(fraction: Fraction, acceleration: Fraction) -> Fraction:
    require(0 <= fraction <= 1 and acceleration > 0, "amdahl-domain")
    return 1 / ((1 - fraction) + fraction / acceleration)


def batch_cost(
    setup: Fraction, per_request: Fraction, batch: int, spacing: Fraction
) -> dict[str, Fraction]:
    require(
        type(batch) is int
        and 0 < batch <= 1_000_000
        and setup >= 0
        and per_request >= 0
        and spacing >= 0,
        "batch-domain",
    )
    total = setup + batch * per_request
    filling = Fraction(batch - 1, 2) * spacing
    return {
        "compute": total,
        "amortized_compute": total / batch,
        "mean_filling": filling,
        "mean_completion": total + filling,
        "first_completion": total + (batch - 1) * spacing,
    }
