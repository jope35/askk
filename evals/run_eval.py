#!/usr/bin/env python3
"""Score the bash agent against docs/examples.json.

Standard library only. The agent runs on the host through `opencode run`, the
generated command runs in a Harbor sandbox, and a judge model decides rows that
miss both exact match and the sandbox.
"""

import argparse
import concurrent.futures
import dataclasses
import json
import os
import socket
import subprocess
import sys
import time

DEFAULT_MODEL = "claude-agent/system.ai.claude-haiku-5-5"
DEFAULT_DATASET = "docs/examples.json"
DEFAULT_FIXTURES = "evals/fixtures.json"
DEFAULT_RESULTS = "evals/results"


class HarnessError(Exception):
    """The harness cannot run. maps to exit status 2."""


class AgentError(Exception):
    """One agent call timed out or failed."""


class JudgeError(Exception):
    """One judge call timed out, failed, or gave no yes or no."""


@dataclasses.dataclass
class Config:
    dataset_path: str = DEFAULT_DATASET
    fixtures_path: str = DEFAULT_FIXTURES
    results_dir: str = DEFAULT_RESULTS
    workers: int = 8
    repeat: int = 1
    min_pass_rate: float = 1.0
    smoke: bool = False
    judge_enabled: bool = True
    model: str = DEFAULT_MODEL
    judge_model: str | None = None
    render_docs: bool = False
    server_url: str | None = None


@dataclasses.dataclass
class Row:
    index: int
    category: str
    input: str
    output: str


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--fixtures", default=DEFAULT_FIXTURES)
    parser.add_argument("--results-dir", default=DEFAULT_RESULTS)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--min-pass-rate", type=float, default=1.0)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--no-judge", action="store_true")
    parser.add_argument("--render-docs", action="store_true")
    args = parser.parse_args(argv)
    return Config(
        dataset_path=args.dataset,
        fixtures_path=args.fixtures,
        results_dir=args.results_dir,
        workers=args.workers,
        repeat=args.repeat,
        min_pass_rate=args.min_pass_rate,
        smoke=args.smoke,
        judge_enabled=not args.no_judge,
        model=os.environ.get("ASKK_MODEL", DEFAULT_MODEL),
        judge_model=os.environ.get("ASKK_JUDGE_MODEL"),
        render_docs=args.render_docs,
    )


def load_dataset(path):
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    return [
        Row(index=index, category=item["category"], input=item["input"], output=item["output"])
        for index, item in enumerate(data)
    ]


def load_fixtures(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return {}


def validate_judge_config(config):
    if not config.judge_enabled:
        return
    if not config.judge_model:
        raise HarnessError("ASKK_JUDGE_MODEL is not set and the judge is enabled")
    if config.judge_model == config.model:
        raise HarnessError("ASKK_JUDGE_MODEL must differ from ASKK_MODEL")


def agent_command(config, request):
    command = ["opencode", "run"]
    if config.server_url:
        command += ["--server", config.server_url]
    command += ["--agent", "bash", "--model", config.model, request]
    return command


def call_agent(config, request, run=subprocess.run):
    try:
        proc = run(
            agent_command(config, request),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired as error:
        raise AgentError(f"agent call timed out: {request!r}") from error
    if proc.returncode != 0:
        raise AgentError(
            f"agent call failed with status {proc.returncode}: {request!r}: "
            f"{(proc.stderr or '').strip()[:200]}"
        )
    return proc.stdout


def preflight(config, run=subprocess.run):
    request = "Show git status"

    def check(_index):
        try:
            call_agent(config, request, run)
            return True
        except AgentError:
            return False

    with concurrent.futures.ThreadPoolExecutor(max_workers=config.workers) as pool:
        return all(pool.map(check, range(config.workers)))


def run_agent_calls(config, rows, run=subprocess.run):
    def call(row):
        try:
            return row.index, call_agent(config, row.input, run)
        except AgentError as error:
            return row.index, error

    with concurrent.futures.ThreadPoolExecutor(max_workers=config.workers) as pool:
        return dict(pool.map(call, rows))


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def start_server():
    port = free_port()
    process = subprocess.Popen(
        ["opencode", "serve", "--hostname", "127.0.0.1", "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise HarnessError("opencode serve exited before it accepted connections")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return process, f"http://127.0.0.1:{port}"
        except OSError:
            time.sleep(0.2)
    process.terminate()
    raise HarnessError("opencode serve did not start within 20 seconds")


def stop_server(process):
    if process is None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def setup_transport(config):
    """Return a server process, or None when the direct transport works."""
    if preflight(config):
        return None
    print("preflight failed; falling back to one opencode serve process", file=sys.stderr)
    process, url = start_server()
    config.server_url = url
    if preflight(config):
        return process
    stop_server(process)
    raise HarnessError("preflight failed on both the direct and the server transport")


def select_command(raw):
    """Apply extraction steps 1 and 2: first fence or first non-empty line, trimmed."""
    lines = raw.splitlines()
    for index, line in enumerate(lines):
        if line.strip().startswith("```"):
            body = []
            for inner in lines[index + 1 :]:
                if inner.strip().startswith("```"):
                    break
                body.append(inner.strip())
            return "\n".join(body).strip()
    for line in lines:
        if line.strip():
            return line.strip()
    return ""


def extract_command(raw):
    """Return one valid command, or None when the output breaks the contract."""
    candidate = select_command(raw)
    if not candidate or "\n" in candidate:
        return None
    check = subprocess.run(
        ["bash", "-n"], input=candidate, text=True, capture_output=True
    )
    if check.returncode != 0:
        return None
    return candidate


def exact_match(generated, expected):
    return generated.strip() == expected.strip()


def main(argv=None):
    config = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        validate_judge_config(config)
    except HarnessError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if config.render_docs:
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
