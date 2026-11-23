#!/usr/bin/env python3
"""Spike: do N parallel `opencode run` calls work against the shared background
server, and does the fallback (one `opencode serve` + `opencode run --server URL`)
work? Findings are recorded in docs/eval-spikes.md. Standard library only."""

import argparse
import concurrent.futures
import os
import socket
import subprocess
import time

DEFAULT_MODEL = "claude-agent/system.ai.claude-haiku-5-5"
REQUEST = "Show git status"
TIMEOUT = 30


def call(cmd):
    start = time.monotonic()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return ("timeout", time.monotonic() - start, "", "")
    elapsed = time.monotonic() - start
    if proc.returncode != 0:
        return (f"exit {proc.returncode}", elapsed, proc.stdout.strip()[:200], proc.stderr.strip()[:200])
    return ("ok", elapsed, proc.stdout.strip()[:200], "")


def parallel(cmd_for, n):
    with concurrent.futures.ThreadPoolExecutor(max_workers=n) as pool:
        return list(pool.map(lambda i: call(cmd_for(i)), range(n)))


def wait_for_port(port, server, deadline=20):
    end = time.monotonic() + deadline
    while time.monotonic() < end:
        if server.poll() is not None:
            return False
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.3)
    return False


def report(label, results):
    for i, (status, elapsed, out, err) in enumerate(results):
        print(f"  call {i}: {status} in {elapsed:.1f}s out={out!r} err={err!r}")
    ok = all(r[0] == "ok" for r in results)
    print(f"{label}: {'PASS' if ok else 'FAIL'} ({sum(1 for r in results if r[0] == 'ok')}/{len(results)} ok)")
    return ok


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--port", type=int, default=4799)
    args = parser.parse_args()
    model = os.environ.get("ASKK_MODEL", DEFAULT_MODEL)

    base = ["opencode", "run", "--agent", "bash", "--model", model, REQUEST]
    print(f"phase 1: {args.workers} parallel `opencode run` (shared background server), model={model}")
    phase1 = report("phase 1", parallel(lambda i: base, args.workers))

    print(f"phase 2: one `opencode serve` on port {args.port} + `opencode run --server URL` x{args.workers}")
    server = subprocess.Popen(
        ["opencode", "serve", "--hostname", "127.0.0.1", "--port", str(args.port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        if not wait_for_port(args.port, server):
            print(f"phase 2: FAIL (server did not start, exit={server.poll()})")
            return 1
        url = f"http://127.0.0.1:{args.port}"
        fallback = ["opencode", "run", "--server", url, "--agent", "bash", "--model", model, REQUEST]
        phase2 = report("phase 2", parallel(lambda i: fallback, args.workers))
    finally:
        server.terminate()
        server.wait(timeout=10)
    return 0 if (phase1 and phase2) else 1


if __name__ == "__main__":
    raise SystemExit(main())
