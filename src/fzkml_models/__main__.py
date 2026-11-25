"""Fixed tiny scenarios only; no arbitrary workloads, external data or GPU."""

import argparse

from .experiment import run


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, choices=[1, 2, 3], default=1)
    parser.add_argument("--references-only", action="store_true")
    args = parser.parse_args()
    return run(args.repetitions, args.references_only)


if __name__ == "__main__":
    raise SystemExit(main())
