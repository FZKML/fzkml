"""Original tiny integer/Paillier/replicated-sharing references, not production crypto."""

from __future__ import annotations

import math
import secrets
from dataclasses import dataclass


def exact_product(a: int, b: int) -> int:
    if any(type(v) is not int or abs(v) > 32 for v in (a, b)):
        raise ValueError("signed-integer-workload-domain")
    return a * b


def probable_prime(n: int, rounds: int = 64) -> bool:
    if n < 2:
        return False
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n % p == 0:
            return n == p
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for _ in range(rounds):
        a = secrets.randbelow(n - 3) + 2
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True


def prime(bits: int) -> int:
    while True:
        candidate = secrets.randbits(bits) | (1 << (bits - 1)) | 1
        if probable_prime(candidate):
            return candidate


@dataclass(frozen=True)
class Paillier:
    n: int
    secret_lambda: int
    secret_mu: int

    @classmethod
    def generate(cls, bits: int = 2048) -> Paillier:
        if type(bits) is not int or bits not in (2048, 3072):
            raise ValueError("research-key-profile")
        while True:
            p, q = prime(bits // 2), prime(bits // 2)
            n = p * q
            lam = math.lcm(p - 1, q - 1)
            if p != q and n.bit_length() == bits and math.gcd(lam, n) == 1:
                return cls(n, lam, pow(lam, -1, n))

    def encrypt(self, message: int) -> int:
        if type(message) is not int or abs(message) > 1024 or 2 * abs(message) >= self.n:
            raise ValueError("signed-plaintext-domain")
        r = secrets.randbelow(self.n - 1) + 1
        while math.gcd(r, self.n) != 1:
            r = secrets.randbelow(self.n - 1) + 1
        return ((1 + self.n * (message % self.n)) * pow(r, self.n, self.n**2)) % self.n**2

    def check_ciphertext(self, c: int) -> None:
        if type(c) is not int or not 0 < c < self.n**2 or math.gcd(c, self.n) != 1:
            raise ValueError("noncanonical-or-nonunit-ciphertext")

    def multiply_public(self, c: int, coefficient: int) -> int:
        self.check_ciphertext(c)
        if type(coefficient) is not int or abs(coefficient) > 32:
            raise ValueError("coefficient-domain")
        return pow(c, coefficient, self.n**2)

    def decrypt(self, c: int) -> int:
        self.check_ciphertext(c)
        value = pow(c, self.secret_lambda, self.n**2)
        if (value - 1) % self.n:
            raise ValueError("invalid-L-domain")
        residue = ((value - 1) // self.n * self.secret_mu) % self.n
        signed = residue if 2 * residue <= self.n else residue - self.n
        if abs(signed) > 1024:
            raise ValueError("decoded-workload-domain")
        return signed


def replicated_views(secret: int, p: int = 17) -> tuple[tuple[int, int], ...]:
    if type(secret) is not int or not 0 <= secret < p or p != 17:
        raise ValueError("tiny-reference-field")
    x, y = secrets.randbelow(p), secrets.randbelow(p)
    z = (secret - x - y) % p
    return ((x, y), (y, z), (z, x))


def coalition_reconstruct(views: tuple[tuple[int, int], ...], p: int = 17) -> int:
    if len(views) != 2 or views[0][1] != views[1][0]:
        raise ValueError("two-adjacent-replicated-views-required")
    return (sum(views[0]) + views[1][1]) % p


def require_prover_profile(corrupt: int, passive: bool, shares: int) -> None:
    if type(corrupt) is not int or not 0 <= corrupt <= 1 or passive is not True or shares != 3:
        raise ValueError("requires-three-parties-and-at-most-one-passive-corruption")


def sumcheck_counterexample(variables: int, claimed_sum: int, p: int = 17) -> dict[str, object]:
    if type(variables) is not int or not 1 <= variables <= 8 or p != 17:
        raise ValueError("bounded-field-reference")
    claim = claimed_sum % p
    rounds = []
    for _ in range(variables):
        constant = claim * pow(2, -1, p) % p
        rounds.append({"constant": constant, "local_consistency": 2 * constant % p == claim})
        claim = constant
    return {
        "rounds": rounds,
        "terminal_claim": claim,
        "unbound_verifier_accepts": True,
        "intended_zero_polynomial": 0,
        "bound_terminal_check_accepts": claim == 0,
    }
