# askk evaluation harness specification

This document specifies a program that measures the askk agent against known examples. The agent lives in `.opencode/agents/bash.md` and turns one request into one Bash command. The file `docs/examples.json` lists example requests with the expected command for each. An evaluation run scores the agent on each request.

## Goals

The program must do all of the following:

- Run every request in `docs/examples.json` through the agent in parallel.
- Execute each generated command in a sandbox and report whether it ran properly, yes or no.
- Also compare each generated command with the expected command. An output match counts as a pass even when the row has no sandbox fixture.
- Print the pass rate overall and one pass rate per category.
- Exit with status 1 when the pass rate falls below a threshold. The threshold comes from a command line flag.

## Non-goals

- The program does not modify the agent prompt.
- The program does not optimize prompts or train models.
- The program does not grade rows whose generated command needs machine state that the sandbox fixture does not provide. Those rows pass or fail on output match alone.

## Approaches

Two approaches are used, one per leg of the yes/no.

1. MLflow GenAI evaluation. This leg compares text. The `mlflow.genai.evaluate` function takes a dataset and a list of scorers. The dataset comes from `docs/examples.json`. A code-based scorer compares each output with the expectation and returns yes or no. MLflow stores every row and every scorer result in a run, so results stay comparable across runs and models.
2. Harbor. This leg executes in a sandbox. Each example becomes one Harbor task: `instruction.md` holds the request, `environment/` holds a container with the fixtures the command needs, and `tests/` runs the generated command and writes a reward to the verifier log. Harbor runs tasks in parallel with `--n-concurrent`. Harbor earns its place here because execution needs isolation. The examples include deletion, process kills, and `sudo`, and none of them may touch the host.
3. A plain Python script with a thread pool. Not chosen. It would reinvent dataset handling, scoring, and result storage that MLflow provides, and it offers no sandbox.

## Design

### Files

- `evals/run_eval.py` is the runner. It loads `docs/examples.json`, runs the agent calls in parallel, scores every result, prints a report, and exits with a status code.
- `evals/requirements.txt` lists the Python dependencies. The only new dependency is `mlflow`.
- `evals/test_run_eval.py` holds unit tests for the extraction, normalization, and scoring functions.

### Dataset

Each row of `docs/examples.json` becomes one evaluation row:

- `inputs.request` holds the natural language request.
- `expectations.expected_command` holds the expected Bash command.
- The category stays in the row so the report can group results by it.

`docs/examples.json` is the only file the harness reads. `docs/examples.md` is a rendered copy of the same data. Generate one file from the other. Do not edit both by hand.

### Running the agent in parallel

The runner uses a thread pool from `concurrent.futures`. The pool size comes from the `--workers` flag, default 8. Each task runs this command:

```
opencode run --agent bash --model MODEL REQUEST
```

The model comes from the `ASKK_MODEL` environment variable, default `claude-agent/system.ai.claude-haiku-5-5`, the same default as `askk.sh`. Each call gets a timeout of 30 seconds. The 2 second budget in `docs/agent-spec.md` applies to interactive use only.

Before the run, the runner makes `--workers` parallel calls with the request `Show git status`. If any of them fails, the runner prints the failure and exits with status 2. This preflight catches a shared lock, a port conflict, or missing credentials before the dataset runs.

The OpenCode docs do not prove that parallel `opencode run` calls are safe, because the CLI can use one shared background server and one shared database. If the preflight fails, the fallback is one `opencode serve` process plus `opencode run --attach URL` for every worker.

A call that times out, hits a rate limit, or fails to authenticate counts as an error, not as a no. Errors print as error and leave the pass rate. If any error occurs, the runner exits with status 2 after printing the report.

### Executing in the sandbox

Each example also runs as one Harbor task. The agent inside the container is the same askk pipeline: `opencode run --agent bash --model MODEL REQUEST`, followed by the same extraction. The verifier writes reward 1 when the generated command exits 0, and reward 0 otherwise.

Refusal rows are the exception. Their expected output starts with `! printf` and exits 1 by design, with a diagnostic on stderr. For those rows the verifier writes reward 1 when the command exits 1 and stderr carries the expected message prefix.

A row gets a sandbox fixture only when its command needs machine state, for example `/var/log/nginx`, `./src`, or a git repository. Rows without a fixture pass or fail on output match alone. The fixture map lives in `evals/fixtures.json` so the harness and the docs stay in one place.

### Extracting the command

The model output can contain prose or a fenced code block. The runner applies the full extraction and validation from `askk.sh`:

1. Take the first fenced code block when one is present, otherwise take the first non-empty line.
2. Trim spaces from both ends.
3. Reject the command when it spans more than one line.
4. Reject the command when `bash -n` reports a syntax error.

A rejected command counts as an error, not as a no. The unit tests pin this extraction against the awk logic in `askk.sh`, so the runner cannot drift from the wrapper.

### Scorers

The scorers are:

- `exact_match` trims the generated command and the expected command and compares them. It returns yes on equality and no otherwise.
- `normalized_match` collapses runs of whitespace and compares. It is informational only. The runner never gates on it, because collapsing spaces inside quotes changes the meaning of a command.
- `semantic_judge` asks an LLM judge whether the generated command performs the same operation as the expected command. The judge is on by default. Disable it with `--no-judge`. MLflow ships an `Equivalence` scorer that can serve as this judge.

Pass rule: a row passes when the output match says yes (exact match, or the judge when enabled), or when the sandbox execution says yes. The report prints the match column, the execution column, and the final yes or no. The pass rate and the exit status use the final yes or no only.

The refusal rows in `docs/examples.json` contain free-form reason text, so exact match alone can never pass them. The judge model comes from `ASKK_JUDGE_MODEL`. If `ASKK_JUDGE_MODEL` equals `ASKK_MODEL`, the runner exits with status 2, because a model must not judge itself.

### Report

The runner prints one line per example: category, yes or no, the expected command, and the generated command truncated to 80 characters. It then prints the pass rate overall and one pass rate per category. It logs the full result table to an MLflow experiment named `askk-evals`.

The `--repeat N` flag runs each example N times, default 1. The report shows the fraction of runs that pass for each example. Because the dataset is not verified, the report also lists rows that fail in every repeat as candidate dataset bugs, separate from agent failures.

Exit statuses: 0 means the pass rate is at or above `--min-pass-rate`, default 1.0, and no errors occurred. 1 means the pass rate is below the threshold. 2 means the harness itself failed: missing credentials, a failed preflight, or any error row.

### Safety

Generated commands execute only inside the Harbor sandbox container, never on the host. The host-side runner only compares text. The sandbox has no network route to the host and no mounted host directories. The agent itself keeps all tool permissions denied, as in `.opencode/agents/bash.md`.

## Testing the harness

The unit tests cover three functions: command extraction, whitespace normalization, and the exact match scorer. A smoke mode, `--smoke`, runs five examples so the harness can be tried without a full run.

## Left to the builder

- Pin the MLflow version in `evals/requirements.txt`. On that version, make sure that `mlflow.genai.evaluate` accepts rows that already contain `outputs` and runs scorers without a predict function. The current MLflow API reference supports this. If the pinned version does not, pass a predict function and let the MLflow thread pool supply the parallelism.
- Spike the parallel `opencode run` question before the full build: run the preflight by hand and record whether the shared server or database serializes or fails the calls.
- Pick the judge model for `ASKK_JUDGE_MODEL`. It must be stronger than the model under test.
- Decide whether CI sets `ASKK_MODEL` and the provider credentials. Without them every row is an error and the run exits 2.

## Answers recorded

1. Yes or no means the command runs properly in a sandbox. An output match also counts as a pass.
2. The gate is the combined pass rule above. An output match alone passes a row.
3. The dataset is not verified. Rows that fail in every repeat are flagged as candidate dataset bugs.
