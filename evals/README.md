# Evaluation harness

`evals/run_eval.py` scores the `bash` agent in `.opencode/agents/bash.md` against every request in `docs/examples.json`. The runner uses the Python standard library only. The generated commands run only in a Harbor sandbox container, never on the host.

## Requirements

- Python 3.
- The `opencode` CLI with a provider that serves the agent model and the judge model.
- The `harbor` CLI, Docker, and the Docker buildx plugin.

## Run

From the repository root:

```bash
ASKK_MODEL=provider/agent-model ASKK_JUDGE_MODEL=provider/judge-model python3 evals/run_eval.py
```

The runner checks the judge configuration, runs a preflight with `--workers` parallel agent calls, calls the agent for every request, executes each generated command in Harbor, and sends rows that miss exact match and the sandbox to the judge. It prints one line per row, the overall pass rate, and one pass rate per category. It writes the full table to `evals/results/<UTC timestamp>.json`.

A run that stops before the first agent call writes no results file. A run where every row is an error prints no pass rate.

## Examples and Harbor tasks

Each entry in `docs/examples.json` becomes one Harbor task:

- `id` is the task directory name and the task name `askk/<id>`. It has 1 to 32 characters from `a-z`, `0-9`, and `-`, because Harbor cuts trial names at 32 characters. The report and the results file show the id.
- `setup` is an optional shell script. The Dockerfile of the task runs it, so the sandbox has the files that the command needs.
- `expect` is optional. Without it, the command must exit 0. With `clarify` or `refuse`, the command must exit 1 and print `Clarify:` or `Cannot generate a safe command:` to stderr.

The repository commits the generated tasks in `evals/tasks/`. After you change `docs/examples.json`, run both commands, because each call handles one flag:

```bash
python3 evals/run_eval.py --build-tasks
python3 evals/run_eval.py --render-docs
```

A unit test fails when `evals/tasks/` does not match `docs/examples.json`. `harbor view --tasks evals/tasks` browses the definitions, and `harbor task start-env evals/tasks/<id>` opens a shell in one task's container.

## Environment variables

- `ASKK_MODEL` is the agent model. The default is `claude-agent/system.ai.claude-haiku-5-5`, the same default as `askk.sh`. Set it when your provider does not serve that model.
- `ASKK_JUDGE_MODEL` is the judge model. The judge is on by default. An unset value is an error. A value equal to `ASKK_MODEL` is an error, because a model must not judge itself.
- The provider credentials must be available to `opencode`. Without them every agent call fails, every row is an error, and the run exits with status 2.

## Flags

- `--dataset PATH` reads another dataset. The default is `docs/examples.json`.
- `--results-dir PATH` writes the results file elsewhere. The default is `evals/results`.
- `--workers N` sets the agent and Harbor concurrency. The default is 8.
- `--repeat N` runs every example N times. The default is 1.
- `--min-pass-rate R` sets the pass threshold. The default is 1.0.
- `--smoke` runs only the first five examples.
- `--no-judge` turns the judge off. The judge model is not needed then.
- `--build-tasks [DIR]` writes one Harbor task directory per example to `DIR` and exits 0. The default is `evals/tasks`. Each task holds the expected command, so you can read every task before a run, or run them with `harbor run -p DIR --agent nop`. The flag replaces every task folder in `DIR`, and it refuses a folder that holds anything else, with exit status 2. It ignores `--smoke` and always writes every example.
- `--reference` runs the expected command of every example in Harbor and prints each task that does not pass. Use it after you change an example or its setup. It exits 0 when all tasks pass, 1 when a task fails, and 2 when Harbor gives no reward.
- `--render-docs` regenerates `docs/examples.md` from `docs/examples.json` and exits 0. Do not edit `docs/examples.md` by hand.

## Exit statuses

- 0: the pass rate is at or above `--min-pass-rate` and no row is an error.
- 1: the pass rate is below `--min-pass-rate`.
- 2: the harness failed. Examples are a judge configuration error, a failed preflight and a failed fallback, a missing sandbox, or any error row.

The highest status wins: 2 over 1 over 0.

## Tests

```bash
python3 -m unittest discover -s evals -v
```
