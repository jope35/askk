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

## Environment variables

- `ASKK_MODEL` is the agent model. The default is `claude-agent/system.ai.claude-haiku-5-5`, the same default as `askk.sh`. Set it when your provider does not serve that model.
- `ASKK_JUDGE_MODEL` is the judge model. The judge is on by default. An unset value is an error. A value equal to `ASKK_MODEL` is an error, because a model must not judge itself.
- The provider credentials must be available to `opencode`. Without them every agent call fails, every row is an error, and the run exits with status 2.

## Flags

- `--dataset PATH` reads another dataset. The default is `docs/examples.json`.
- `--fixtures PATH` reads another fixture map. The default is `evals/fixtures.json`.
- `--results-dir PATH` writes the results file elsewhere. The default is `evals/results`.
- `--workers N` sets the agent and Harbor concurrency. The default is 8.
- `--repeat N` runs every example N times. The default is 1.
- `--min-pass-rate R` sets the pass threshold. The default is 1.0.
- `--smoke` runs only the first five examples.
- `--no-judge` turns the judge off. The judge model is not needed then.
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
