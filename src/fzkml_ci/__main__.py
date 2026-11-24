"""Public CLI: diagnostics contain error codes, never raw data or environments."""

import argparse
import sys
from pathlib import Path

from .report import verify_report, write_report
from .validate import Invalid, load


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["report", "verify-report", "workflow-policy"])
    parser.add_argument("--results", type=Path, default=Path("examples/results.json"))
    parser.add_argument("--claims", type=Path, default=Path("examples/claims.json"))
    parser.add_argument("--output", type=Path, default=Path("dist"))
    args = parser.parse_args()
    try:
        if args.command == "report":
            write_report(load(args.results), load(args.claims), args.output)
        elif args.command == "verify-report":
            verify_report(args.output)
        else:
            from .workflow import check_repository

            check_repository()
    except Invalid as error:
        print(f"validation failed: {error}", file=sys.stderr)
        return 1
    except (OSError, ValueError, RecursionError, SyntaxError, KeyError, TypeError):
        print("validation failed: malformed-input-or-filesystem", file=sys.stderr)
        return 1
    print("validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
