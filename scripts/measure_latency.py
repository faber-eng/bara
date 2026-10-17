#!/usr/bin/env python3
import argparse
import json
import math
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_URL = "https://ai-builder-cup-511906.web.app"
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "docs/eval/latency_live.json"
PATHS = (
    "/api/health",
    "/api/public/riau/summary",
    "/api/public/riau/cells?limit=200",
    "/api/public/riau/bulletin",
    "/api/tiles/drying?region=riau",
)
REQUESTS_PER_PATH = 20
PAUSE_S = 1.1
TIMEOUT_S = 60
EXIT_FAILED = 1


def nearest_rank(values, share):
    ordered = sorted(values)
    return ordered[max(math.ceil(share * len(ordered)) - 1, 0)]


def cache_busted(base, path):
    joiner = "&" if "?" in path else "?"
    return f"{base}{path}{joiner}nocache={uuid.uuid4().hex}"


def timed_get(url):
    started = time.perf_counter()
    with urllib.request.urlopen(url, timeout=TIMEOUT_S) as response:
        response.read()
        status = response.status
    return status, (time.perf_counter() - started) * 1000.0


def measure(base, path, count, pause_s):
    timings = []
    for _ in range(count):
        status, elapsed_ms = timed_get(cache_busted(base, path))
        if status != 200:
            raise RuntimeError(f"{path} returned {status}")
        timings.append(elapsed_ms)
        time.sleep(pause_s)
    return {
        "path": f"GET {path}",
        "p50_ms": round(nearest_rank(timings, 0.5), 1),
        "p95_ms": round(nearest_rank(timings, 0.95), 1),
        "n": len(timings),
        "where": "live URL, sequential, cache-busting query so the Hosting CDN is skipped",
        "source": "scripts/measure_latency.py",
    }


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Time the public GET routes of the live deployment (no sign-in) "
        "and write docs/eval/latency_live.json."
    )
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--count", type=int, default=REQUESTS_PER_PATH)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    run_at = datetime.now(UTC).isoformat()
    try:
        rows = [measure(args.url, path, args.count, PAUSE_S) for path in PATHS]
    except (urllib.error.URLError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_FAILED
    report = {"run_at": run_at, "url": args.url, "paths": rows}
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
