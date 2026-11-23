#!/usr/bin/env python3
"""Spike: can a Harbor task run an injected command in tests/ and report a
reward, without a real agent phase? Builds three task directories (a command
that exits 0, one that exits 1, and a refusal-style command), runs them with
one harbor job, and prints the rewards it finds. Findings go to
docs/eval-spikes.md. Standard library only."""

import argparse
import json
import os
import shutil
import subprocess
import sys

TASK_TOML = """schema_version = "1.4"

[task]
name = "spike/{name}"

[environment]
network_mode = "no-network"

[verifier]
timeout_sec = 120.0

[agent]
timeout_sec = 60.0
"""

DOCKERFILE = "FROM ubuntu:24.04\nWORKDIR /app\n"

TEST_SH = """#!/bin/bash
# Runs the injected command and writes a reward to /logs/verifier/reward.txt.
mkdir -p /logs/verifier
cd /app
cmd="$(cat /tests/command.txt)"
bash -c "$cmd" >/tmp/out.txt 2>/tmp/err.txt
rc=$?
reward=0
if [ "$rc" -eq 0 ]; then
  reward=1
fi
prefix='__PREFIX__'
if [ -n "$prefix" ] && [ "$rc" -eq 1 ]; then
  n=${#prefix}
  if [ "$(head -c "$n" /tmp/err.txt)" = "$prefix" ]; then
    reward=1
  fi
fi
printf '%s\\n' "$reward" > /logs/verifier/reward.txt
"""

CASES = [
    ("ok", "true", ""),
    ("fail", "false", ""),
    ("refusal", "! printf 'Clarify: %s\\n' 'Which path?' >&2", "Clarify:"),
]


def build_tasks(root):
    tasks_dir = os.path.join(root, "tasks")
    for name, command, prefix in CASES:
        task_dir = os.path.join(tasks_dir, name)
        os.makedirs(os.path.join(task_dir, "environment"), exist_ok=True)
        os.makedirs(os.path.join(task_dir, "tests"), exist_ok=True)
        with open(os.path.join(task_dir, "task.toml"), "w") as f:
            f.write(TASK_TOML.replace("{name}", name))
        with open(os.path.join(task_dir, "instruction.md"), "w") as f:
            f.write(f"Run the command for case {name}.\n")
        with open(os.path.join(task_dir, "environment", "Dockerfile"), "w") as f:
            f.write(DOCKERFILE)
        with open(os.path.join(task_dir, "tests", "test.sh"), "w") as f:
            f.write(TEST_SH.replace("__PREFIX__", prefix))
        with open(os.path.join(task_dir, "tests", "command.txt"), "w") as f:
            f.write(command + "\n")
    return tasks_dir


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="/tmp/opencode/harbor-spike")
    parser.add_argument("--jobs-dir", default=None)
    args = parser.parse_args()
    root = os.path.abspath(args.root)
    shutil.rmtree(root, ignore_errors=True)
    tasks_dir = build_tasks(root)
    jobs_dir = args.jobs_dir or os.path.join(root, "jobs")

    cmd = [
        "harbor", "run", "-p", tasks_dir,
        "--agent", "nop",
        "-n", str(len(CASES)),
        "-o", jobs_dir,
        "--yes",
    ]
    print("run:", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    print(proc.stdout[-3000:])
    print(proc.stderr[-2000:], file=sys.stderr)
    print(f"harbor exit: {proc.returncode}")

    print("reward files found:")
    found = {}
    for dirpath, _dirnames, filenames in os.walk(jobs_dir):
        for filename in filenames:
            if "reward" in filename:
                path = os.path.join(dirpath, filename)
                with open(path) as f:
                    found[path] = f.read().strip()
                print(f"  {path}: {found[path]}")
    if not found:
        print("  none; jobs dir contents:")
        for dirpath, dirnames, filenames in os.walk(jobs_dir):
            for filename in filenames:
                print("  ", os.path.join(dirpath, filename))
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
