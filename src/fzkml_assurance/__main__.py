from __future__ import annotations

import argparse

from . import authenticity, benchmark, golden, reporting


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=["golden", "proof", "benchmark", "report", "review-check"]
    )
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--require-reviewed", action="store_true")
    parser.add_argument("--repetitions", type=int, choices=[1, 2], default=1)
    args = parser.parse_args()
    if args.command == "golden":
        return golden.run(args.write)
    if args.command == "proof":
        return authenticity.run()
    if args.command == "benchmark":
        return benchmark.run(args.repetitions)
    if args.command == "report":
        return reporting.build(args.check)
    reporting.validate_review(reporting.review_packet(), args.require_reviewed)
    print("Scope packet valid; independent review is still pending.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TypeError):
        print("Assurance command failed closed; inspect its bounded manifest/status.")
        raise SystemExit(1) from None
