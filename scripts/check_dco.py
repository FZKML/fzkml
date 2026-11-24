"""Require author and coauthor DCO sign-offs for each new PR commit."""
import argparse
import re
import subprocess
import sys


def identity(value):
    match = re.fullmatch(r"\s*(\S(?:.*\S)?)\s+<([^\s<>]+@[^\s<>]+)>\s*", value)
    if not match:
        raise ValueError("invalid identity: " + value)
    return (match[1].strip().casefold(), match[2].casefold())


def check_message(author, message):
    trailers = subprocess.check_output(
        ["git", "interpret-trailers", "--parse"], input=message.encode()
    ).decode()
    signed = set()
    required = {identity(author)}
    for line in trailers.splitlines():
        key, separator, value = line.partition(":")
        if separator and key.casefold() == "signed-off-by":
            signed.add(identity(value.strip()))
        if separator and key.casefold() == "co-authored-by":
            required.add(identity(value.strip()))
    missing = required - signed
    if missing:
        raise ValueError("missing Signed-off-by trailer for " + repr(sorted(missing)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", help="base commit SHA")
    parser.add_argument("head", help="head commit SHA")
    args = parser.parse_args()
    # Immutable IDs avoid option/ref ambiguity in untrusted inputs.
    for value in (args.base, args.head):
        if not re.fullmatch(r"[0-9a-f]{40,64}", value):
            parser.error("base and head must be full commit SHAs")
    commits = subprocess.check_output(
        ["git", "rev-list", args.base + ".." + args.head]
    ).decode().splitlines()
    failures = []
    for commit in commits:
        author = subprocess.check_output(["git", "show", "-s", "--format=%an <%ae>", commit]).decode().strip()
        message = subprocess.check_output(["git", "show", "-s", "--format=%B", commit]).decode()
        try:
            check_message(author, message)
        except ValueError as error:
            failures.append(commit + ": " + str(error))
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("DCO trailers verified for %s commit(s)" % len(commits))
    return 0


if __name__ == "__main__":
    sys.exit(main())
