"""One fixed public logical client. Delays emulate service, not hardware."""

from __future__ import annotations

import json
import sys
import time

from reference.numeric import encode, evaluate


def main() -> int:
    if len(sys.argv) != 3:
        return 2
    index, delay = int(sys.argv[1]), int(sys.argv[2])
    if index not in range(3) or delay not in {0, 10, 200}:
        return 2
    time.sleep(delay / 1000)
    xs, ys = [16, -8, 24], [16, -16, 8]
    trace = evaluate(encode(8, [xs[index]] * 3, [ys[index]] * 3, [1] * 3))
    updates = trace["updates"]
    assert isinstance(updates, list)
    print(json.dumps({"index": index, "update": updates[0], "emulated_delay_ms": delay}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
