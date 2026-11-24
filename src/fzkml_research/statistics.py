"""Binomial test inversion using positive Decimal sums, not a normal approximation."""

from __future__ import annotations

import math
from decimal import Decimal, localcontext

from fzkml_ci.validate import require


def _count(k: int, n: int) -> None:
    require(
        type(k) is int and type(n) is int and 0 <= k <= n <= 20_000 and n > 0,
        "binomial-count-range",
    )


def _tail(k: int, n: int, p: Decimal) -> Decimal:
    """P[Binomial(n,p)>=k]; caller provides a high precision local context."""
    if k <= 0:
        return Decimal(1)
    if k > n or p == 0:
        return Decimal(0)
    if p == 1:
        return Decimal(1)
    q = 1 - p
    term = Decimal(math.comb(n, k)) * p**k * q ** (n - k)
    total = term
    for j in range(k, n):
        term *= Decimal(n - j) * p / (Decimal(j + 1) * q)
        total += term
    return min(Decimal(1), total)


def binomial_tail(k: int, n: int, p: float) -> float:
    require(
        type(n) is int and 0 < n <= 20_000 and type(k) is int and 0 <= k <= n + 1,
        "binomial-count-range",
    )
    require(math.isfinite(p) and 0 <= p <= 1, "binomial-probability")
    with localcontext() as ctx:
        ctx.prec = 80
        return float(_tail(k, n, Decimal(str(p))))


def lower_bound(k: int, n: int, error: float) -> float:
    """One-sided Clopper-Pearson lower bound; error is the tail error, not coverage.

    Exact refers to the statistical method. Numerical inversion uses 80 decimal
    digits and 80 bisections; this is not a machine-verified interval arithmetic proof.
    """
    _count(k, n)
    require(math.isfinite(error) and 1e-12 <= error < 1, "binomial-error-budget")
    if k == 0:
        return 0.0
    with localcontext() as ctx:
        ctx.prec = 80
        lo, hi, target = Decimal(0), Decimal(1), Decimal(str(error))
        for _ in range(80):
            middle = (lo + hi) / 2
            if _tail(k, n, middle) < target:
                lo = middle
            else:
                hi = middle
        return max(0.0, math.nextafter(float(lo), -math.inf))


def upper_bound(k: int, n: int, error: float) -> float:
    _count(k, n)
    value = 1 - lower_bound(n - k, n, error)
    return min(1.0, math.nextafter(value, math.inf))


def rate_test_power(
    n: int, null_rate: float, alternative_rate: float, error: float
) -> dict[str, float | int | str]:
    """Power of a predeclared upper-tail event-rate test, not of the complete DP audit."""
    require(0 <= null_rate < alternative_rate <= 1 and 0 < error < 1, "power-design")
    lo, hi = 0, n + 1
    while lo < hi:
        middle = (lo + hi) // 2
        if binomial_tail(middle, n, null_rate) <= error:
            hi = middle
        else:
            lo = middle + 1
    return {
        "method": "one-sided-binomial-event-rate-test",
        "critical_events": lo,
        "power": binomial_tail(lo, n, alternative_rate),
        "limitation": "This is event-rate test power, not joint DP-audit power.",
    }
