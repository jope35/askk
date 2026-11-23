#!/usr/bin/env python3
"""Score the bash agent against docs/examples.json.

Standard library only. The agent runs on the host through `opencode run`, the
generated command runs in a Harbor sandbox, and a judge model decides rows that
miss both exact match and the sandbox.
"""

import argparse
import concurrent.futures
import datetime
import dataclasses
import json
import os
import shlex
import socket
import subprocess
import sys
import tempfile
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


def stop_server(process):
    if process is None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


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


def call_agent(config, request, run=subprocess.run):
    cmd = ["opencode", "run"]
    if config.server_url:
        cmd += ["--server", config.server_url]
    cmd += ["--agent", "bash", "--model", config.model, request]
    try:
        proc = run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired as error:
        raise AgentError(f"agent call timed out after 30s: {request}") from error
    except OSError as error:
        raise AgentError(f"agent call failed to start: {error}") from error
    if proc.returncode != 0:
        detail = (proc.stderr or "").strip().splitlines()[-1:] or ["no stderr"]
        raise AgentError(f"agent call exited {proc.returncode}: {detail[0]}")
    return proc.stdout


def preflight(config, run=subprocess.run):
    def one(_):
        try:
            call_agent(config, "Show git status", run=run)
            return True
        except AgentError:
            return False

    with concurrent.futures.ThreadPoolExecutor(max_workers=config.workers) as pool:
        return all(pool.map(one, range(config.workers)))


def run_agent_calls(config, rows, run=subprocess.run):
    def one(row):
        try:
            return row.index, call_agent(config, row.input, run=run)
        except AgentError as error:
            return row.index, error

    with concurrent.futures.ThreadPoolExecutor(max_workers=config.workers) as pool:
        return dict(pool.map(one, rows))


JUDGE_PROMPT = """Grade whether the generated Bash command fulfils the request.

Request:
{request}

Expected command:
{expected}

Generated command:
{generated}

The generated command may differ from the expected command in quoting or flag order. Answer only Yes or No.
"""


def judge_prompt(row, generated):
    return JUDGE_PROMPT.format(request=row.input, expected=row.output, generated=generated)


def judge_row(config, row, generated, run=subprocess.run):
    cmd = ["opencode", "run"]
    if config.server_url:
        cmd += ["--server", config.server_url]
    cmd += ["--model", config.judge_model, judge_prompt(row, generated)]
    try:
        proc = run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired as error:
        raise JudgeError(f"judge call timed out for {row.input!r}") from error
    except OSError as error:
        raise JudgeError(f"judge call failed to start: {error}") from error
    if proc.returncode != 0:
        raise JudgeError(f"judge call exited {proc.returncode}: {(proc.stderr or '').strip()[:200]}")
    answer = select_command(proc.stdout).lower()
    if answer not in ("yes", "no"):
        raise JudgeError(f"judge answered neither yes nor no: {proc.stdout.strip()[:200]!r}")
    return answer


def run_judge(config, jobs, run=subprocess.run):
    def one(job):
        row, generated = job
        try:
            return row.index, judge_row(config, row, generated, run=run)
        except JudgeError as error:
            return row.index, error

    with concurrent.futures.ThreadPoolExecutor(max_workers=config.workers) as pool:
        return dict(pool.map(one, jobs))


def start_server(host="127.0.0.1"):
    with socket.socket() as probe:
        probe.bind((host, 0))
        port = probe.getsockname()[1]
    proc = subprocess.Popen(
        ["opencode", "serve", "--hostname", host, "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            break
        try:
            with socket.create_connection((host, port), timeout=1):
                return f"http://{host}:{port}", proc
        except OSError:
            time.sleep(0.2)
    proc.terminate()
    proc.wait(timeout=10)
    raise HarnessError("fallback opencode serve did not start")


def start_transport(config, run=subprocess.run):
    """Return the fallback server process, or None when direct calls work."""
    if preflight(config, run=run):
        return None
    print("preflight failed; switching to opencode serve fallback", file=sys.stderr)
    url, proc = start_server()
    config.server_url = url
    if preflight(config, run=run):
        return proc
    proc.terminate()
    proc.wait(timeout=10)
    raise HarnessError("fallback transport failed its preflight")


def is_refusal(row):
    return row.output.strip().startswith("! printf")


def refusal_prefix(expected):
    if "Cannot generate a safe command:" in expected:
        return "Cannot generate a safe command:"
    if "Clarify:" in expected:
        return "Clarify:"
    return None


VERIFIER_TEMPLATE = """#!/bin/bash
set -u
mkdir -p /logs/verifier
cd /app
cmd="$(cat /tests/command.txt)"
timeout 30 bash -c "$cmd" >/tmp/askk-stdout 2>/tmp/askk-stderr
rc=$?
prefix=__PREFIX__
if [ -n "$prefix" ] && [ "$rc" -eq 1 ] && [ "$(head -c ${#prefix} /tmp/askk-stderr)" = "$prefix" ]; then
  echo 1 > /logs/verifier/reward.txt
elif [ -z "$prefix" ] && [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
"""

TASK_TOML = """schema_version = "1.4"

[verifier]
timeout_sec = 120.0

[agent]
timeout_sec = 60.0

[environment]
network_mode = "no-network"
build_timeout_sec = 600.0
"""


def verifier_script(row):
    prefix = refusal_prefix(row.output) if is_refusal(row) else ""
    return VERIFIER_TEMPLATE.replace("__PREFIX__", shlex.quote(prefix or ""))


def build_task_dir(workspace, row, fixture, command):
    task_dir = os.path.join(workspace, f"row-{row.index}")
    os.makedirs(os.path.join(task_dir, "environment"), exist_ok=True)
    os.makedirs(os.path.join(task_dir, "tests"), exist_ok=True)
    with open(os.path.join(task_dir, "task.toml"), "w", encoding="utf-8") as handle:
        handle.write(TASK_TOML)
    with open(os.path.join(task_dir, "instruction.md"), "w", encoding="utf-8") as handle:
        handle.write(row.input + "\n")
    dockerfile = "FROM ubuntu:24.04\nWORKDIR /app\n"
    setup = (fixture or {}).get("setup")
    if setup:
        dockerfile += "RUN <<'SETUP'\nset -eu\n" + setup + "\nSETUP\n"
    with open(os.path.join(task_dir, "environment", "Dockerfile"), "w", encoding="utf-8") as handle:
        handle.write(dockerfile)
    with open(os.path.join(task_dir, "tests", "command.txt"), "w", encoding="utf-8") as handle:
        handle.write(command + "\n")
    test_path = os.path.join(task_dir, "tests", "test.sh")
    with open(test_path, "w", encoding="utf-8") as handle:
        handle.write(verifier_script(row))
    os.chmod(test_path, 0o755)
    return task_dir


def parse_rewards(jobs_dir, task_names):
    found = {}
    for dirpath, _dirnames, filenames in os.walk(jobs_dir):
        if "reward.txt" not in filenames or os.path.basename(dirpath) != "verifier":
            continue
        trial = os.path.basename(os.path.dirname(dirpath))
        for name in task_names:
            if trial.startswith(name + "__"):
                with open(os.path.join(dirpath, "reward.txt"), encoding="utf-8") as handle:
                    value = handle.read().strip()
                found[name] = "yes" if value in ("1", "1.0") else "no"
    return {name: found.get(name, "error") for name in task_names}


def run_sandbox(config, jobs):
    fixtures = load_fixtures(config.fixtures_path)
    workspace = tempfile.mkdtemp(prefix="askk-eval-")
    tasks_dir = os.path.join(workspace, "tasks")
    jobs_dir = os.path.join(workspace, "jobs")
    for row, command in jobs:
        build_task_dir(tasks_dir, row, fixtures.get(row.input), command)
    cmd = [
        "harbor", "run", "-p", tasks_dir, "--agent", "nop",
        "--n-concurrent", str(config.workers), "-o", jobs_dir,
        "--job-name", "askk-eval", "--yes",
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"warning: harbor failed: {error}", file=sys.stderr)
    names = {f"row-{row.index}": row.index for row, _command in jobs}
    rewards = parse_rewards(jobs_dir, list(names))
    return {names[name]: rewards[name] for name in names}


def score_row(match, sandbox, judge):
    if "yes" in (match, sandbox, judge):
        return "yes"
    if "error" in (match, sandbox, judge):
        return "error"
    return "no"


def compute_exit(passed, total, errors, min_pass_rate):
    if errors:
        return 2
    if total == 0:
        return 2
    if passed / total < min_pass_rate:
        return 1
    return 0


def write_results(results_dir, table):
    os.makedirs(results_dir, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(results_dir, f"{stamp}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(table, handle, indent=2)
        handle.write("\n")
    return path


def render_report(table, repeat=1):
    lines = []
    for item in table:
        generated = item["generated"] or ""
        if len(generated) > 80:
            generated = generated[:77] + "..."
        label = item["category"]
        if repeat > 1:
            label = f"{label} [{item['repeat'] + 1}/{repeat}]"
        lines.append(
            f"{label} | match={item['match']} exec={item['sandbox']} "
            f"judge={item['judge']} final={item['final']} | "
            f"expected: {item['output']} | generated: {generated}"
        )
    scored = [item for item in table if item["final"] != "error"]
    lines.append("")
    if scored:
        passed = sum(1 for item in scored if item["final"] == "yes")
        lines.append(f"pass rate: {passed}/{len(scored)} = {passed / len(scored):.1%}")
        categories = {}
        for item in scored:
            counts = categories.setdefault(item["category"], [0, 0])
            counts[0] += item["final"] == "yes"
            counts[1] += 1
        for category in sorted(categories):
            yes, total = categories[category]
            lines.append(f"  {category}: {yes}/{total} = {yes / total:.1%}")
    else:
        lines.append("every row is an error; no rate printed")
    bugs = []
    for index in sorted({item["index"] for item in table}):
        runs = [item for item in table if item["index"] == index]
        if len(runs) > 1 and all(item["final"] == "no" for item in runs):
            bugs.append(runs[0]["input"])
    if bugs:
        lines.append("candidate dataset bugs (failed every repeat, no errors):")
        lines.extend(f"  {bug}" for bug in bugs)
    return "\n".join(lines)


def run(config):
    try:
        validate_judge_config(config)
    except HarnessError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    try:
        rows = load_rows(config)
    except (OSError, ValueError) as error:
        print(f"error: cannot load dataset: {error}", file=sys.stderr)
        return 2
    server = None
    try:
        server = start_transport(config)
    except HarnessError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    try:
        table = []
        for repeat_index in range(config.repeat):
            calls = run_agent_calls(config, rows)
            work = {}
            for row in rows:
                raw = calls[row.index]
                if isinstance(raw, AgentError):
                    work[row.index] = (None, "no")
                    table.append(
                        {
                            "index": row.index,
                            "repeat": repeat_index,
                            "category": row.category,
                            "input": row.input,
                            "output": row.output,
                            "generated": None,
                            "match": "error",
                            "sandbox": "error",
                            "judge": "error",
                            "final": "error",
                            "error": str(raw),
                        }
                    )
                    continue
                generated = extract_command(raw)
                if generated is None:
                    work[row.index] = (None, "no")
                    continue
                work[row.index] = (generated, "yes" if exact_match(generated, row.output) else "no")
            sandbox_jobs = [
                (row, work[row.index][0])
                for row in rows
                if work.get(row.index) and work[row.index][0] is not None
            ]
            sandbox = run_sandbox(config, sandbox_jobs) if sandbox_jobs else {}
            judge_jobs = [
                (row, work[row.index][0])
                for row in rows
                if work.get(row.index)
                and work[row.index][0] is not None
                and work[row.index][1] != "yes"
                and sandbox.get(row.index) != "yes"
                and sandbox.get(row.index) != "error"
            ]
            judged = run_judge(config, judge_jobs) if (config.judge_enabled and judge_jobs) else {}
            for row in rows:
                if any(
                    item["index"] == row.index and item["repeat"] == repeat_index
                    for item in table
                ):
                    continue
                generated, match = work.get(row.index, (None, "no"))
                execution = sandbox.get(row.index, "no") if generated is not None else "no"
                verdict = "no"
                if config.judge_enabled and row.index in judged:
                    result = judged[row.index]
                    verdict = "error" if isinstance(result, JudgeError) else result
                elif isinstance(judged.get(row.index), JudgeError):
                    verdict = "error"
                final = score_row(match, execution, verdict)
                table.append(
                    {
                        "index": row.index,
                        "repeat": repeat_index,
                        "category": row.category,
                        "input": row.input,
                        "output": row.output,
                        "generated": generated,
                        "match": match,
                        "sandbox": execution,
                        "judge": verdict,
                        "final": final,
                        "error": None,
                    }
                )
    finally:
        stop_server(server)
    print(render_report(table, config.repeat))
    path = write_results(config.results_dir, table)
    print(f"results: {path}")
    scored = [item for item in table if item["final"] != "error"]
    passed = sum(1 for item in scored if item["final"] == "yes")
    errors = sum(1 for item in table if item["final"] == "error")
    return compute_exit(passed, len(scored), errors, config.min_pass_rate)


EXAMPLES_HEADER = """# Example requests

One hundred natural-language requests and the one-line Bash command the agent should return.

Grounded in `docs/agent-spec.md` and `.opencode/agents/bash.md`. Devin Desktop Terminal Command is the UX analog: natural language in the terminal (`Cmd`/`Ctrl+I`) yields CLI syntax, then the user reviews before run ([Command overview](https://docs.devin.ai/desktop/command/windsurf-overview), [Terminal](https://docs.devin.ai/desktop/terminal.md)). Categories follow public NL-to-shell tools (Copilot CLI `suggest`, Warp AI Command Search): files, find, git, docker, processes, jq/text, systemd, curl, tar/rsync, failed-command repair, and refuse-or-clarify.

Format matches the agent prompt: Input, then Output. Each output is one syntactically complete Bash line: no fences, no preamble, no here-document.

"""


def truncate_rows(rows, smoke):
    return rows[:5] if smoke else rows


def load_rows(config):
    return truncate_rows(load_dataset(config.dataset_path), config.smoke)


def render_examples_md(rows):
    parts = [EXAMPLES_HEADER]
    category = None
    for row in rows:
        if row.category != category:
            category = row.category
            parts.append(f"## {category}\n\n")
        parts.append(f"Input: {row.input}\nOutput: {row.output}\n\n")
    text = "".join(parts)
    return text[:-1] if text.endswith("\n\n") else text


def write_examples_md(rows, path):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(render_examples_md(rows))
    return path


def main(argv=None):
    config = parse_args(sys.argv[1:] if argv is None else argv)
    if config.render_docs:
        try:
            rows = load_rows(config)
        except (OSError, ValueError) as error:
            print(f"error: cannot load dataset: {error}", file=sys.stderr)
            return 2
        path = os.path.join(os.path.dirname(config.dataset_path), "examples.md")
        print(f"wrote {write_examples_md(rows, path)}")
        return 0
    return run(config)

if __name__ == "__main__":
    raise SystemExit(main())
