"""Bounded CPU float64 comparison; exact verification remains entirely in Rust."""

from __future__ import annotations

import hashlib
import math
import platform
import struct
import time
from fractions import Fraction
from pathlib import Path
from typing import Any

import torch

from . import CONTRACT_VERSION, CanonicalBatch, ResearchSession


def export_tensors(
    model: torch.nn.Module, x: torch.Tensor, y: torch.Tensor, counts: tuple[int, int, int]
) -> tuple[CanonicalBatch, float]:
    if (
        type(model) is not torch.nn.Linear
        or model.in_features != 1
        or model.out_features != 1
        or model.bias is not None
    ):
        raise ValueError("unsupported-operator: require Linear(1,1,bias=False)")
    if x.shape != (3, 1) or y.shape != (3, 1) or model.weight.shape != (1, 1):
        raise ValueError("unsupported-shape")
    if (
        "forward" in vars(model)
        or model._modules
        or model._forward_hooks
        or model._forward_pre_hooks
        or model._backward_hooks
        or model.weight._backward_hooks
        or getattr(model.weight, "_post_accumulate_grad_hooks", None)
    ):
        raise ValueError("unsupported-hooks-or-overrides")
    tensors = (model.weight, x, y)
    if not model.weight.requires_grad or any(t.layout != torch.strided for t in tensors):
        raise ValueError("unsupported-frozen-model-or-layout")
    if any(t.device.type != "cpu" or t.dtype != torch.float64 for t in tensors):
        raise ValueError("unsupported-device-or-dtype")
    if len(counts) != 3 or any(type(n) is not int or not 1 <= n <= 4 for n in counts):
        raise ValueError("count-range")
    # At most seven scalar values cross to Python. No data-dependent large allocation.
    values = [
        float(model.weight.detach().item()),
        *x.detach().flatten().tolist(),
        *y.detach().flatten().tolist(),
    ]
    if any(not math.isfinite(v) or not -2 <= v <= 2 for v in values):
        raise ValueError("nonfinite-or-out-of-range")
    quantized = [round(Fraction.from_float(v) * 16) for v in values]
    data = b"FZKNUM01" + struct.pack("<HHIq", 1, 3, 16, quantized[0])
    for i in range(3):
        data += struct.pack("<qqI", quantized[1 + i], quantized[4 + i], counts[i])
    error = max(abs(v - q / 16) for v, q in zip(values, quantized, strict=True))
    return CanonicalBatch(data), error


def profile_tiny(
    model: torch.nn.Module,
    x: torch.Tensor,
    y: torch.Tensor,
    counts: tuple[int, int, int],
    seed: int = 7,
) -> dict[str, Any]:
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("seed-range")
    start = time.perf_counter()
    batch, export_error = export_tensors(model, x, y, counts)
    conversion_seconds = time.perf_counter() - start
    previous = torch.are_deterministic_algorithms_enabled()
    previous_warn_only = torch.is_deterministic_algorithms_warn_only_enabled()
    trained = []
    initial_weight = float(model.weight.detach().item())
    start = time.perf_counter()
    try:
        with torch.random.fork_rng(devices=[]):
            torch.default_generator.manual_seed(seed)
            torch.use_deterministic_algorithms(True)
            for i in range(3):
                client = torch.nn.Linear(1, 1, bias=False, dtype=torch.float64)
                with torch.no_grad():
                    client.weight.fill_(initial_weight)
                optimizer = torch.optim.SGD(
                    client.parameters(),
                    lr=0.25,
                    momentum=0,
                    dampening=0,
                    weight_decay=0,
                    nesterov=False,
                    foreach=False,
                )
                optimizer.zero_grad(set_to_none=True)
                loss = ((client(x[i : i + 1]) - y[i : i + 1]) ** 2).sum() / 2
                loss.backward()
                optimizer.step()
                trained.append(float(client.weight.detach().item()))
    finally:
        torch.use_deterministic_algorithms(previous, warn_only=previous_warn_only)
    training_seconds = time.perf_counter() - start
    float_output = sum(n * w for n, w in zip(counts, trained, strict=True)) / sum(counts)
    start = time.perf_counter()
    session = ResearchSession()
    setup_seconds = time.perf_counter() - start
    result = session.prove(batch)
    start = time.perf_counter()
    accepted = session.verify(batch, result)
    verification_seconds = time.perf_counter() - start
    root = Path(__file__).resolve().parents[2]
    # Reproduction identifiers are populated by the repository runner, not invented
    # when an installed wheel is used outside a checkout.
    digests = {}
    for name in ("Cargo.lock", "uv.lock", "specs/numeric-contract-v1.json"):
        path = root / name
        if path.is_file():
            digests[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "profile_schema": "fzkml-tiny-profile-1.0.0",
        "contract_version": CONTRACT_VERSION,
        "fixture_version": "numeric-v1",
        "scope": "public synthetic CPU fixture; exploratory quality comparison",
        "backend": "ark-groth16-0.5.0-bn254",
        "security_mode": "research-local-random-setup",
        "model": "Linear(1,1,bias=False)",
        "optimizer": "SGD(lr=1/4,momentum=0,weight_decay=0)",
        "preprocessor": "identity",
        "dtype": "torch.float64",
        "fixture_seed": seed,
        "deterministic_algorithms": True,
        "deterministic_portability_guarantee": False,
        "versions": {"python": platform.python_version(), "torch": torch.__version__},
        "platform": {
            "system": platform.system(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "torch_threads": torch.get_num_threads(),
        },
        "digests": digests,
        "key_id": result.key_id,
        "parameters_id": session.parameters_id,
        "proof_valid": accepted,
        "proof_bytes": len(result.proof),
        "quality": {
            "floating_aggregate": float_output,
            "integer_aggregate": result.output,
            "dequantized_aggregate": result.output / 16,
            "absolute_training_difference": abs(float_output - result.output / 16),
            "max_input_quantization_error": export_error,
        },
        "seconds": {
            "training": training_seconds,
            "conversion_and_copying": conversion_seconds,
            "host_witness_generation": result.witness_seconds,
            "proving": result.proving_seconds,
            "setup": setup_seconds,
            "verification": verification_seconds,
        },
        "limitations": [
            "one sample per client; counts are declared aggregation weights",
            "all relation inputs public; no training-data privacy claim",
            "proving time includes backend constraint synthesis and QAP witness mapping",
            "one tiny fixture and one repetition; not a throughput benchmark",
            "no accelerator proposal; no production setup or reviewed security claim",
        ],
    }
