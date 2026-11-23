# askk evaluation harness specification

This document specifies a program that measures the askk agent against known examples. The agent lives in `.opencode/agents/bash.md` and turns one request into one Bash command. The file `docs/examples.json` lists example requests with the expected command for each. An evaluation run scores the agent on each request.

## Goals

- Run every request in `docs/examples.json` through the agent in parallel.
- Execute each generated command in a sandbox and report whether it ran properly, yes or no.
- Also compare each generated command with the expected command. An exact match counts as a pass even when the row has no fixture.
- Print the pass rate overall and one pass rate per category.
- Exit with status 1 when the pass rate falls below a threshold. The threshold comes from a command line flag.

## Non-goals

- The program does not modify the agent prompt.
- The program does not optimize prompts or train models.
- The program does not detect which machine state a generated command needs. A row whose fixture lacks that state gets reward 0 from the sandbox, and the judge decides whether the command is correct.
- The program does not compute a whitespace-normalized match. It was informational only.

## Approaches

The harness has two legs: text comparison and sandbox execution. Harbor runs the execution leg in every approach, because execution needs isolation. The examples include deletion, process kills, and `sudo`, and none of them may touch the host.

The open choice was the text leg.

1. A standard-library-only runner (chosen). The runner loads the dataset with `json.load`, compares text with plain functions, prints the report, and writes one JSON results file per run. It adds no dependency.
2. MLflow GenAI evaluation. Not chosen. MLflow supplies dataset handling, scorer dispatch, and run storage, but the runner needs each of those in a few lines, and MLflow is the one heavyweight dependency in the design. It also carries a version risk: `mlflow.genai.evaluate` must accept rows that already contain `outputs` and must run scorers without a predict function. Its `Equivalence` judge is replaced by one `opencode run` call to the judge model.
3. No judge. Not chosen. Many correct commands differ from the expected text in quoting or flag order, so the pass rate would read lower than the agent deserves.

## Design

### Files

- `evals/run_eval.py` is the runner. It uses the standard library only. It loads `docs/examples.json`, runs the agent calls in parallel, scores every result, prints a report, writes a results file, and exits with a status code.
- `evals/results/` receives one JSON file per run, named with the UTC timestamp of the run.
- `evals/test_run_eval.py` holds unit tests for the extraction and the exact match scorer.

There is no `requirements.txt`: the runner needs no package beyond the standard library.

### Dataset

The runner reads `docs/examples.json` as it is. Each row is one evaluation row: `id` names its Harbor task, `input` holds the request, `output` holds the expected Bash command, and `category` groups the report. The optional `setup` and `expect` fields describe the sandbox and the verifier rule. `docs/examples.md` is a rendered copy of the same data. Generate `docs/examples.md` from `docs/examples.json`. Do not edit `docs/examples.md` by hand.

### Running the agent

The runner calls the agent once per example and per repeat, through a thread pool from `concurrent.futures`. The pool size comes from the `--workers` flag, default 8. Each task runs this command:

```
opencode run --agent bash --model MODEL REQUEST
```

The model comes from the `ASKK_MODEL` environment variable, default `claude-agent/system.ai.claude-haiku-5-5`, the same default as `askk.sh`. Each call gets a timeout of 30 seconds. The 2 second budget in `docs/agent-spec.md` applies to interactive use only.

Before the run, the runner makes `--workers` parallel calls with the request `Show git status`. This preflight catches a shared lock, a port conflict, or missing credentials before the dataset runs. If any call fails, the runner prints the failure and switches to the fallback transport: one `opencode serve` process plus `opencode run --server URL` for every worker. The run exits with status 2 only when the fallback also fails or cannot start.

The OpenCode docs do not prove that parallel `opencode run` calls are safe, because the CLI can use one shared background server and one shared database. The fallback exists for that risk.

A call that times out, hits a rate limit, or fails to authenticate counts as an error, not as a no. Errors print as error and do not enter the pass rate: the pass rate is the fraction of scored rows that pass. When every row is an error, the runner prints no pass rate. If any error occurs, the runner exits with status 2 after printing the report.

Each scored command comes from exactly one agent call on the host. The runner never runs the agent inside the sandbox, so no credentials enter the sandbox and the scored command cannot drift from the executed one.

### Executing in the sandbox

Each example runs as one Harbor task. The runner writes the task directory: `instruction.md` holds the request, `environment/` holds a container with the fixture the command needs, and `tests/` runs the generated command and writes a reward to the verifier log. The verifier writes reward 1 when the command exits 0, and reward 0 otherwise. Harbor runs the tasks in parallel with `--n-concurrent`.

`evals/tasks/` holds a committed, generated copy of every task, and a unit test keeps it in step with `docs/examples.json`.

A row gets a fixture only when its command needs machine state, for example `/var/log/nginx`, `./src`, or a git repository. The fixture is the `setup` field of the row in `docs/examples.json`. A fixture must make the expected command pass, and `run_eval.py --reference` makes sure that it does. Every row without a fixture, refusal or not, runs in a bare container. The `id` field of the row names its task directory and its Harbor task. The `expect` field selects the verifier rule.

Refusal rows are the exception to the exit 0 rule. The runner marks a row as a refusal row when its expected command starts with `! printf`. Those commands exit 1 by design, with a diagnostic on stderr. For a refusal row the verifier writes reward 1 when the command exits 1 and stderr starts with the diagnostic prefix from the row's expected command, `Cannot generate a safe command:` or `Clarify:`.

### Extracting the command

The model output can contain prose or a fenced code block. The runner applies the full extraction and validation from the output contract in `docs/agent-spec.md`:

1. Take the first fenced code block when one is present, otherwise take the first non-empty line.
2. Trim spaces from both ends.
3. Reject the command when it spans more than one line.
4. Reject the command when `bash -n` reports a syntax error.

A rejected command counts as a no, not as an error. The agent broke its output contract, so the row fails. There is no command to execute or judge. The unit tests pin steps 1 and 2 against the awk logic in `askk.sh` and steps 3 and 4 against the list above, so the runner cannot drift from the wrapper.

### Scoring

The scorers are:

- `exact_match` trims the generated command and the expected command and compares them. It returns yes on equality and no otherwise.
- `sandbox` returns yes when the verifier wrote reward 1 for the generated command.
- `judge` runs only on rows that fail both `exact_match` and `sandbox`: one `opencode run` call to the judge model with the request, the expected command, and the generated command, answered yes or no. The judge call runs without `--agent bash`, because the bash agent must return a command, not a verdict. The judge is on by default. Disable it with `--no-judge`. The judge model comes from `ASKK_JUDGE_MODEL`. With the judge enabled, an unset `ASKK_JUDGE_MODEL` is an error, and `ASKK_JUDGE_MODEL` equal to `ASKK_MODEL` is an error, because a model must not judge itself. Both errors exit with status 2. The judge call gets the same 30 second timeout as an agent call. A judge call that fails, times out, or answers neither yes nor no counts as an error, not as a no.

Pass rule: a row passes when `exact_match` says yes, or `sandbox` says yes, or `judge` says yes. The pass rate and the exit status use the final yes or no only.

The reason text inside a refusal command is free-form, so the generated refusal rarely matches the expected command word for word. Refusal rows pass through sandbox execution or the judge.

### Run order

1. Validate the judge configuration: with the judge enabled, `ASKK_JUDGE_MODEL` must be set and must differ from `ASKK_MODEL`.
2. Run the preflight, and on failure switch to the fallback transport.
3. Call the agent for every example and repeat, then extract the command and score `exact_match`.
4. Run every sandbox task and score `sandbox`.
5. Run the judge on the rows where both scorers said no.
6. Print the report, write the results file, and exit.

A configuration or preflight failure stops the run before scoring. Agent, sandbox, and judge errors are collected while the run continues, so the report stays complete.

### Report

The runner prints one line per example: category, the match, execution, and judge columns, the final yes or no, the expected command, and the generated command truncated to 80 characters. It then prints the pass rate overall and one pass rate per category. It writes the full result table, every column included, to `evals/results/TIMESTAMP.json`. A run that stops before the first agent call writes no results file.

The `--repeat N` flag runs each example N times, default 1. Each run counts as one row in the pass rate. The report shows the fraction of runs that pass for each example. Because the dataset is not verified, the report also lists rows that fail in every repeat as candidate dataset bugs, separate from agent failures. A row that errors in every repeat is an error row, not a candidate dataset bug.

Exit statuses: 0 means the pass rate is at or above `--min-pass-rate`, default 1.0, and no errors occurred. 1 means the pass rate is below the threshold. 2 means the harness itself failed: missing credentials, a failed preflight with a failed fallback, a judge configuration error, or any error row. When more than one condition applies, the highest status wins: 2 over 1 over 0.

### Safety

Generated commands execute only inside the Harbor sandbox container, never on the host. On the host, the runner compares text and runs `bash -n`, which parses the command without executing it. The sandbox has no network route to the host and no mounted host directories. The model call and its credentials stay on the host. The sandbox runs the generated command only. The agent itself keeps all tool permissions denied, as in `.opencode/agents/bash.md`.

## Testing the harness

The unit tests cover the command extraction and the exact match scorer. A smoke mode, `--smoke`, runs the first five examples of the dataset so the harness can be tried without a full run.

## Left to the builder

- Confirm that a Harbor task can skip its agent phase, or run a no-op agent, when `tests/` already runs the injected command. If Harbor requires an agent inside the container, run the agent there once instead, read the generated command from the task log, and drop the host-side agent calls.
- Spike the parallel `opencode run` question before the full build: run the preflight by hand and record whether the shared server or database serializes or fails the calls. Also confirm that `opencode serve` and `opencode run --server URL` work as the fallback needs, because the docs do not prove the flags.
- `askk.sh` implements only extraction steps 1 and 2. It lacks the multi-line reject and the `bash -n` check that `docs/agent-spec.md` specifies. Add both, or the wrapper and the runner accept different outputs.
- `docs/agent-spec.md` says the agent may run read-only inspection tools, but `.opencode/agents/bash.md` denies every tool. Resolve the contradiction. The eval measures `bash.md` as it is.
- Decide whether sandbox tasks have internet access. The network examples fetch from public hosts, which is flaky in a repeatable run. Serve their fixtures locally, or let the judge decide those rows.
- Pick the judge model for `ASKK_JUDGE_MODEL`. It must be stronger than the model under test.
- Decide whether CI sets `ASKK_MODEL` and the provider credentials. Without them every row is an error and the run exits 2.

## Answers recorded

1. Yes or no means the command runs properly in a sandbox. An exact match also counts as a pass.
2. The gate is the combined pass rule above. An exact match alone passes a row.
3. The dataset is not verified. Rows that fail in every repeat are flagged as candidate dataset bugs.
4. MLflow is out. The text leg is standard library only, results go to a JSON file, and the judge is one `opencode run` call, used only on rows that miss both exact match and sandbox execution.
