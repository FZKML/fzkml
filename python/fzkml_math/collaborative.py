"""Bounded external coCircom adapter; accepts only the pinned real verifier result."""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import struct
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

SOURCE_COMMIT = "97adcc06afc0d506c2d6aa9f81b2e342fd8108c0"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sections(data: bytes, magic: bytes) -> dict[int, bytes]:
    if (
        data[:4] != magic
        or len(data) < 12
        or struct.unpack_from("<I", data, 4)[0] != (2 if magic == b"wtns" else 1)
    ):
        raise ValueError("canonical-circom-header")
    count = struct.unpack_from("<I", data, 8)[0]
    if count > 8:
        raise ValueError("bounded-section-count")
    result, offset = {}, 12
    for _ in range(count):
        kind, size = struct.unpack_from("<IQ", data, offset)
        offset += 12
        if kind in result or size > len(data) - offset:
            raise ValueError("invalid-or-duplicate-section")
        result[kind] = data[offset : offset + size]
        offset += size
    if offset != len(data):
        raise ValueError("trailing-section-bytes")
    return result


def inspect_multiplier(source: Path) -> dict[str, Any]:
    """Independently parse the pinned R1CS and witness, not an upstream prose circuit."""
    root = source / "test_vectors/Groth16/bn254/multiplier2"
    r = sections((root / "circuit.r1cs").read_bytes(), b"r1cs")
    w = sections((root / "witness.wtns").read_bytes(), b"wtns")
    h = r[1]
    width = struct.unpack_from("<I", h)[0]
    if width != 32 or len(h) != 64:
        raise ValueError("unsupported-field-header")
    p = int.from_bytes(h[4:36], "little")
    if p != 21888242871839275222246405745257275088548364400416034343698204186575808495617:
        raise ValueError("not-BN254-scalar-field")
    wires, public_out, public_in, private_in, labels, constraints = struct.unpack_from(
        "<IIIIQI", h, 36
    )
    if (wires, public_out, public_in, private_in, labels, constraints) != (4, 1, 0, 2, 4, 1):
        raise ValueError("not-the-pinned-private-two-input-product")
    if w[1][:36] != h[:36] or struct.unpack_from("<I", w[1], 36)[0] != 4 or len(w[2]) != 128:
        raise ValueError("witness-field-or-shape-mismatch")
    witness = [int.from_bytes(w[2][i : i + 32], "little") for i in range(0, 128, 32)]
    if any(v >= p for v in witness):
        raise ValueError("noncanonical-field-witness")
    offset = 0
    forms = []
    for _ in range(3):
        length = struct.unpack_from("<I", r[2], offset)[0]
        offset += 4
        if length != 1:
            raise ValueError("unexpected-multiplier-form")
        index = struct.unpack_from("<I", r[2], offset)[0]
        coefficient = int.from_bytes(r[2][offset + 4 : offset + 36], "little")
        forms.append((index, coefficient))
        offset += 36
    if forms != [(2, p - 1), (3, 1), (1, p - 1)] or offset != len(r[2]):
        raise ValueError("unrecognized-product-constraint")
    if witness[0] != 1 or witness[2] * witness[3] % p != witness[1]:
        raise ValueError("unsatisfied-witness")
    if witness != [1, 33, 3, 11]:
        raise ValueError("unexpected-public-synthetic-inputs")
    return {
        "relation": "a*b=y mod BN254-Fr",
        "integer_domain": "abs(a),abs(b)<=32; abs(y)<=1024",
        "witness": witness,
        "public_inputs": [33],
        "field_modulus": str(p),
        "public_outputs": 1,
        "public_input_variables": 0,
        "private_inputs": 2,
        "constraints": 1,
        "r1cs_sha256": sha(root / "circuit.r1cs"),
        "witness_sha256": sha(root / "witness.wtns"),
    }


class Relay:
    """Loopback TCP byte counter. Counts framed application bytes, not IP overhead."""

    def __init__(self, destination: int, delay: float = 0) -> None:
        self.destination = destination
        self.delay = delay
        self.lock = threading.Lock()
        self.bytes = 0
        self.connections = 0
        self.errors: list[str] = []
        self.stop = threading.Event()
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        self.sock.listen()
        self.sock.settimeout(0.1)
        self.threads: list[threading.Thread] = []
        self.sockets: list[socket.socket] = []
        self.thread = threading.Thread(target=self.accept, daemon=True)
        self.thread.start()

    def copy(self, a: socket.socket, b: socket.socket) -> None:
        try:
            while not self.stop.is_set():
                try:
                    data = a.recv(65536)
                except TimeoutError:
                    continue
                if not data:
                    break
                if self.delay:
                    time.sleep(self.delay)
                b.sendall(data)
                with self.lock:
                    self.bytes += len(data)
        except OSError as exc:
            if not self.stop.is_set():
                self.errors.append(type(exc).__name__)
        finally:
            try:
                b.shutdown(socket.SHUT_WR)
            except OSError:
                pass

    def accept(self) -> None:
        while not self.stop.is_set():
            try:
                a, _ = self.sock.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            deadline = time.monotonic() + 5
            while True:
                try:
                    b = socket.create_connection(("127.0.0.1", self.destination), timeout=0.2)
                    break
                except ConnectionRefusedError:
                    if time.monotonic() > deadline or self.stop.wait(0.01):
                        a.close()
                        return
            a.settimeout(0.2)
            b.settimeout(0.2)
            self.sockets.extend([a, b])
            self.connections += 1
            for x, y in ((a, b), (b, a)):
                t = threading.Thread(target=self.copy, args=(x, y), daemon=True)
                self.threads.append(t)
                t.start()

    def close(self) -> None:
        self.stop.set()
        self.sock.close()
        for s in self.sockets:
            s.close()
        self.thread.join(timeout=1)
        for t in self.threads:
            t.join(timeout=1)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def invoke(binary: Path, args: list[str], timeout: float = 30) -> dict[str, Any]:
    start = time.perf_counter()
    try:
        r = subprocess.run(
            [str(binary), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "RUST_LOG": "info", "RAYON_NUM_THREADS": "1"},
        )
        return {
            "returncode": r.returncode,
            "seconds": time.perf_counter() - start,
            "stdout": r.stdout,
            "stderr": r.stderr,
            "status": "completed",
        }
    except subprocess.TimeoutExpired:
        return {
            "returncode": None,
            "seconds": time.perf_counter() - start,
            "stdout": "",
            "stderr": "",
            "status": "timeout",
        }


def public_transcript(proof: Path, public: Path) -> dict[str, Any]:
    p = json.loads(proof.read_text())
    allowed = {"pi_a", "pi_b", "pi_c", "protocol", "curve"}
    if set(p) != allowed or p["protocol"] != "groth16" or p["curve"] != "bn128":
        raise ValueError("undeclared-public-proof-fields")
    values = json.loads(public.read_text())
    if values != ["33"]:
        raise ValueError("unexpected-public-output")
    return {
        "proof_fields": sorted(p),
        "public_outputs": values,
        "witness_columns_exported": False,
        "limitation": (
            "Field allowlist is not a proof of zero knowledge or absence of side channels."
        ),
    }


def verify(binary: Path, proof: Path, vk: Path, public: Path) -> bool:
    r = invoke(
        binary,
        [
            "verify",
            "groth16",
            "--proof",
            str(proof),
            "--vk",
            str(vk),
            "--public-input",
            str(public),
            "--curve",
            "BN254",
        ],
    )
    return r["returncode"] == 0 and "Proof verified successfully" in r["stdout"]


def prove(
    source: Path,
    binary: Path,
    output: Path,
    *,
    delay: float = 0,
    missing: bool = False,
    malformed: bool = False,
    timeout: float = 15,
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=False)
    vector = source / "test_vectors/Groth16/bn254/multiplier2"
    start = time.perf_counter()
    split = invoke(
        binary,
        [
            "split-witness",
            "--witness",
            str(vector / "witness.wtns"),
            "--r1cs",
            str(vector / "circuit.r1cs"),
            "--protocol",
            "REP3",
            "--curve",
            "BN254",
            "--out-dir",
            str(output),
        ],
    )
    if split["returncode"] != 0:
        raise ValueError("external-witness-splitting-failed")
    if malformed:
        (output / "witness.wtns.1.shared").write_bytes(b"malformed-public-test-share")
    real = [free_port() for _ in range(3)]
    relays = [Relay(p, delay) for p in real]
    processes = []
    records = []
    deadline = time.monotonic() + timeout
    try:
        for i in range(2 if missing else 3):
            config = f'[network]\nmy_id={i}\nbind_addr="127.0.0.1:{real[i]}"\n'
            for j in range(3):
                config += f'[[network.parties]]\nid={j}\ndns_name="127.0.0.1:{relays[j].port}"\n'
            cp = output / f"party{i}.toml"
            cp.write_text(config)
            args = [
                str(binary),
                "generate-proof",
                "groth16",
                "--witness",
                str(output / f"witness.wtns.{i}.shared"),
                "--zkey",
                str(vector / "circuit.zkey"),
                "--check-zkey",
                "--protocol",
                "REP3",
                "--curve",
                "BN254",
                "--config",
                str(cp),
                "--out",
                str(output / f"proof{i}.json"),
                "--public-input",
                str(output / f"public{i}.json"),
            ]
            # One time utility per party; max RSS is that party's process, not a cluster sum.
            mem = output / f"rss{i}.txt"
            timed = (
                ["/usr/bin/time", "-l"]
                if os.uname().sysname == "Darwin"
                else ["/usr/bin/time", "-v"]
            )
            log = mem.open("w")
            p = subprocess.Popen(
                [*timed, *args],
                stdout=subprocess.PIPE,
                stderr=log,
                text=True,
                start_new_session=True,
                env={**os.environ, "RUST_LOG": "info", "RAYON_NUM_THREADS": "1"},
            )
            processes.append((p, log, time.perf_counter(), mem))
        for i, (p, log, started, mem) in enumerate(processes):
            try:
                out, _ = p.communicate(timeout=max(0.01, deadline - time.monotonic()))
                status = "completed" if p.returncode == 0 else "failed"
            except subprocess.TimeoutExpired:
                import signal

                os.killpg(p.pid, signal.SIGKILL)
                out, _ = p.communicate()
                status = "timeout"
            log.close()
            memory = mem.read_text()
            match = re.search(r"(\d+)\s+maximum resident set size", memory)
            rss = int(match[1]) if match else None
            if os.uname().sysname != "Darwin":
                match = re.search(r"Maximum resident set size \(kbytes\): (\d+)", memory)
                rss = int(match[1]) * 1024 if match else None
            kernel = re.search(r"Generate proof took ([0-9.]+) ms", out)
            records.append(
                {
                    "party": i,
                    "status": status,
                    "returncode": p.returncode,
                    "collection_elapsed_seconds_upper_bound": time.perf_counter() - started,
                    "prover_kernel_ms": float(kernel[1]) if kernel else None,
                    "max_rss_bytes": rss,
                }
            )
        elapsed = time.perf_counter() - start
    finally:
        for p, log, _, _ in processes:
            if p.poll() is None:
                import signal

                os.killpg(p.pid, signal.SIGKILL)
                p.wait()
            log.close()
        # Let forwarding EOF settle before snapshotting counters.
        time.sleep(0.05)
        for relay in relays:
            relay.close()
    complete = len(records) == 3 and all(r["status"] == "completed" for r in records)
    verification_start = time.perf_counter()
    verified = complete and verify(
        binary, output / "proof0.json", vector / "verification_key.json", output / "public0.json"
    )
    if verified and json.loads((output / "public0.json").read_text()) != ["33"]:
        raise ValueError("unexpected-authorized-output")
    return {
        "status": (
            "verified"
            if verified
            else "timeout"
            if any(r["status"] == "timeout" for r in records)
            else "failed"
            if any(r["status"] == "failed" for r in records)
            else "rejected"
            if complete
            else "incomplete"
        ),
        "verified": verified,
        "split_seconds": split["seconds"],
        "proof_and_split_wall_seconds": elapsed,
        "verification_seconds": time.perf_counter() - verification_start if complete else None,
        "end_to_end_seconds": time.perf_counter() - start,
        "relay_delay_per_read_seconds": delay,
        "tcp_payload_bytes": sum(r.bytes for r in relays),
        "tcp_connections": sum(r.connections for r in relays),
        "relay_errors": [e for r in relays for e in r.errors],
        "parties": records,
        "proof_json_bytes": (output / "proof0.json").stat().st_size if verified else None,
        "protocol_rounds": None,
        "round_trip_measurement": "not-instrumented",
        "preprocessing": "trusted-public-fixture-SRS-and-dealer-split; no ceremony measured",
        "retained_artifacts": {p.name: sha(p) for p in output.glob("proof*.json")}
        if verified
        else {},
    }
