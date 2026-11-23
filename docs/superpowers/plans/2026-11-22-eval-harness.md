# askk evaluation harness implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `evals/run_eval.py`, a standard-library-only runner that scores the `bash` agent in `.opencode/agents/bash.md` against every request in `docs/examples.json` using exact match, Harbor sandbox execution, and a judge model, then prints pass rates and exits 0, 1, or 2.

**Architecture:** One runner module with six stages in a fixed order: judge configuration check, transport preflight with a `opencode serve` fallback, parallel agent calls through a thread pool, text scoring (`extract_command` plus `exact_match`), Harbor sandbox execution of each generated command, and a judge call on rows that miss both. The report prints one line per example plus overall and per-category pass rates, and every run writes one JSON file to `evals/results/`.

**Tech Stack:** Python 3 standard library only (no `requirements.txt`), the `opencode` CLI for model calls, the `harbor` CLI with a Docker environment for sandboxed execution, `unittest` for the unit tests, Bash for `askk.sh`.

**Spec:** `docs/eval-spec.md`

## Global Constraints

- `evals/run_eval.py` and `evals/test_run_eval.py` use the Python standard library only. There is no `requirements.txt`.
- The runner files are exactly `evals/run_eval.py`, `evals/fixtures.json`, `evals/results/`, and `evals/test_run_eval.py`. `docs/examples.md` is generated from `docs/examples.json` and never edited by hand.
- Agent model comes from `ASKK_MODEL`, default `claude-agent/system.ai.claude-haiku-5-5`. Judge model comes from `ASKK_JUDGE_MODEL`. With the judge enabled, an unset `ASKK_JUDGE_MODEL` or one equal to `ASKK_MODEL` exits with status 2 before any agent call.
- Each agent and judge call gets a 30 second timeout. `--workers` defaults to 8, `--repeat` to 1, `--min-pass-rate` to 1.0. `--smoke` runs only the first five examples.
- Exit statuses: 0 means pass rate at or above `--min-pass-rate` and no errors, 1 means below the threshold, 2 means the harness itself failed. The highest status wins: 2 over 1 over 0.
- A call that times out, hits a rate limit, or fails to authenticate is an error, not a no. Errors print as error and stay out of the pass rate. When every row is an error, no pass rate prints. A run that stops before the first agent call writes no results file.
- Generated commands run only inside the Harbor container. On the host the runner only compares text and runs `bash -n`.
- Extraction contract: take the first fenced code block when present, otherwise the first non-empty line, trim both ends, reject a multi-line command, reject a command that `bash -n` flags. A rejected command is a no.
- A refusal row is one whose expected command starts with `! printf`. Its verifier writes reward 1 when the command exits 1 and stderr starts with the diagnostic prefix from the expected command.
- The sandbox container gets `network_mode = "none"` in its `task.toml`. Rows that need the public internet pass through exact match or the judge, not the sandbox.
- Unit tests run with `python3 -m unittest discover -s evals -v` from the repository root. `evals/test_run_eval.py` inserts its own directory into `sys.path` and imports `run_eval`.

## Review Focus

- Model output with prose around a fenced block, or no fence at all: extraction steps 1 and 2 must match the awk logic in `askk.sh`, and steps 3 and 4 must reject multi-line and `bash -n` failures. Pinned in Task 4 tests.
- Refusal rows: the generated refusal rarely matches the expected text, so the row must pass through the sandbox prefix check or the judge. Pinned in Task 6 and Task 7 tests.
- A row whose command needs machine state but has no fixture: the sandbox writes reward 0 by design and the judge decides. Pinned in Task 6 tests and exercised by the smoke run in Task 10.
- Agent, sandbox, and judge failures are errors, not noes, and any error row forces exit status 2. Pinned in Task 5, Task 7, and Task 8 tests.
- Judge configuration errors stop the run before the first agent call and write no results file. Pinned in Task 3 and Task 8 tests.

---

### Task 1: Spike the agent transport

**Files:**
- Create: `evals/spike_transport.py`
- Create: `docs/eval-spikes.md`

**Interfaces:**
- Produces: findings recorded in `docs/eval-spikes.md` that Task 5 relies on: whether `--workers` parallel `opencode run` calls succeed or serialize, and whether `opencode serve` plus `opencode run --attach URL` works as the fallback.

- [ ] **Step 1: Write `evals/spike_transport.py`**

  The script reads `ASKK_MODEL` (default `claude-agent/system.ai.claude-haiku-5-5`), runs `N` (default 8) parallel calls of `opencode run --agent bash --model MODEL "Show git status"` with a 30 second timeout through a `concurrent.futures.ThreadPoolExecutor`, prints PASS or FAIL per call, then starts one `opencode serve` process and runs the same calls as `opencode run --attach URL --agent bash --model MODEL "Show git status"`, prints the results, and stops the server.

- [ ] **Step 2: Run it and record the result**

  Run: `python3 evals/spike_transport.py`
  Record the command, the output, and the conclusion in `docs/eval-spikes.md`.

- [ ] **Step 3: Commit**

  ```bash
  git add evals/spike_transport.py docs/eval-spikes.md
  git commit -m "spike: parallel opencode run and serve/attach fallback"
  ```

### Task 2: Spike a Harbor task that runs an injected command without an agent

**Files:**
- Create: `evals/spike_harbor.py`
- Modify: `docs/eval-spikes.md`

**Interfaces:**
- Produces: the exact Harbor invocation and reward mechanism that Task 6 relies on: the task directory layout, the `harbor` command line with `--n-concurrent`, where the reward lands in the jobs directory, and whether the agent phase can be skipped (try `--agent nop`) or needs a no-op run.

- [ ] **Step 1: Write `evals/spike_harbor.py`**

  The script builds three task directories in a temporary workspace, each with `task.toml` (`schema_version = "1.4"`, `[environment] network_mode = "none"`, `[verifier]`, `[agent]`), `instruction.md`, `environment/Dockerfile` (`FROM ubuntu:24.04`), and `tests/test.sh` that runs the command stored in `tests/command.txt` and writes 1 or 0 to `/logs/verifier/reward.txt`. The three commands are `true`, `false`, and `! printf 'Clarify: %s\n' 'Which path?' >&2` (the last one must produce reward 1 under the refusal rule: exit 1 and stderr starting with `Clarify:`). The script then runs the Harbor job over the workspace with `--n-concurrent 3` and prints the reward file it finds per task.

- [ ] **Step 2: Run it and record the result**

  Run: `python3 evals/spike_harbor.py`
  Expected: three rewards, 1, 0, and 1. Record the exact `harbor` invocation, the reward file path inside the jobs directory, and the agent-phase answer in `docs/eval-spikes.md`.

- [ ] **Step 3: Commit**

  ```bash
  git add evals/spike_harbor.py docs/eval-spikes.md
  git commit -m "spike: harbor task running an injected command and reporting reward"
  ```

### Task 3: Runner skeleton, configuration validation, and CLI

**Files:**
- Create: `evals/run_eval.py`
- Create: `evals/fixtures.json` (starts as `{}`)
- Create: `evals/results/.gitkeep`
- Create: `evals/test_run_eval.py`

**Interfaces:**
- Produces: `Config` (dataclass with `dataset_path`, `fixtures_path`, `results_dir`, `workers`, `repeat`, `min_pass_rate`, `smoke`, `judge_enabled`, `model`, `judge_model`), `Row` (dataclass with `index`, `category`, `input`, `output`), `parse_args(argv) -> Config`, `load_dataset(path) -> list[Row]`, `load_fixtures(path) -> dict`, `validate_judge_config(config) -> None` (raises `HarnessError` on a judge configuration problem), and `main(argv) -> int` with the six run stages stubbed except stage 1.

- [ ] **Step 1: Write the failing tests**

  In `evals/test_run_eval.py` (add `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))` then `import run_eval`):
  - `test_parse_args_defaults`: `parse_args([])` gives workers 8, repeat 1, min_pass_rate 1.0, judge_enabled True, model `claude-agent/system.ai.claude-haiku-5-5`, dataset `docs/examples.json`.
  - `test_validate_judge_config_unset`: with `ASKK_JUDGE_MODEL` unset and the judge enabled, `validate_judge_config` raises `HarnessError`.
  - `test_validate_judge_config_same_model`: with `ASKK_JUDGE_MODEL == ASKK_MODEL`, it raises `HarnessError`.
  - `test_validate_judge_config_ok`: distinct judge model passes; `--no-judge` passes with no judge model.
  - `test_load_dataset`: loads `docs/examples.json`, 100 rows, first row has `input` "List all files in this folder".

- [ ] **Step 2: Run the tests to verify they fail**

  Run: `python3 -m unittest discover -s evals -v`
  Expected: FAIL with `AttributeError` or import errors.

- [ ] **Step 3: Implement the skeleton in `evals/run_eval.py`**

  `argparse` with flags `--dataset`, `--fixtures`, `--results-dir`, `--workers` (int, 8), `--repeat` (int, 1), `--min-pass-rate` (float, 1.0), `--smoke`, `--no-judge`, `--render-docs`. `HarnessError` exception for status 2 conditions. `main` calls `validate_judge_config` first and returns 2 on `HarnessError`; later tasks fill in stages 2 through 6.

- [ ] **Step 4: Run the tests to verify they pass**

  Run: `python3 -m unittest discover -s evals -v`
  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add evals/run_eval.py evals/fixtures.json evals/results/.gitkeep evals/test_run_eval.py
  git commit -m "feat: eval runner skeleton with CLI and judge config validation"
  ```

### Task 4: Command extraction and the exact match scorer

**Files:**
- Modify: `evals/run_eval.py`
- Modify: `evals/test_run_eval.py`

**Interfaces:**
- Consumes: `Row` from Task 3.
- Produces: `extract_command(raw: str) -> str | None` (None when the output violates the contract) and `exact_match(generated: str, expected: str) -> bool`. Tasks 5 through 8 use both.

- [ ] **Step 1: Write the failing tests**

  - `test_extract_prefers_first_fenced_block`: raw text with prose, a fenced block containing `ls -la`, then more text returns `ls -la`.
  - `test_extract_falls_back_to_first_non_empty_line`: no fence, blank first line, then `pwd` returns `pwd`.
  - `test_extract_trims`: `"  ls -la  \n"` returns `ls -la`.
  - `test_extract_matches_askk_awk`: for a set of sample outputs, `extract_command` steps 1 and 2 agree with the awk program read out of `askk.sh` (the test extracts the awk program from the file between `awk '` and the closing `'` and runs it through `awk` with `subprocess`).
  - `test_extract_rejects_multiline`: a fenced block with two lines returns None.
  - `test_extract_rejects_syntax_error`: `if true; then` returns None (checked with `bash -n` via `subprocess.run(["bash", "-n"], input=...)`).
  - `test_extract_accepts_pipeline`: `find . -name '*.png' | wc -l` passes.
  - `test_exact_match`: `exact_match("ls -la", "ls -la")` is True, `exact_match("ls -la", "ls")` is False, surrounding whitespace on either side is ignored.

- [ ] **Step 2: Run the tests to verify they fail**

  Run: `python3 -m unittest discover -s evals -v`
  Expected: FAIL, `extract_command` not defined.

- [ ] **Step 3: Implement in `evals/run_eval.py`**

  `extract_command`: split into lines, find the first fenced block (a line whose trimmed form starts with three backticks opens it, the next such line closes it), otherwise take the first non-empty line, strip, return None if the result contains a newline or is empty, then run `bash -n` with the candidate on stdin and return None on a nonzero exit. `exact_match`: compare `generated.strip() == expected.strip()`.

- [ ] **Step 4: Run the tests to verify they pass**

  Run: `python3 -m unittest discover -s evals -v`
  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add evals/run_eval.py evals/test_run_eval.py
  git commit -m "feat: command extraction and exact match scorer with tests"
  ```

### Task 5: Agent transport with preflight and fallback

**Files:**
- Modify: `evals/run_eval.py`
- Modify: `evals/test_run_eval.py`

**Interfaces:**
- Consumes: `Config`, `Row` from Task 3; the transport findings in `docs/eval-spikes.md` from Task 1.
- Produces: `AgentError` exception, `preflight(config) -> bool`, and `call_agent(config, request, run=subprocess.run) -> str` that builds `opencode run --agent bash --model MODEL REQUEST` (or the `--attach URL` fallback form when the preflight failed) with a 30 second timeout and raises `AgentError` on timeout or nonzero exit. `run_agent_calls(config, rows) -> dict[int, str | AgentError]` fans out over a `ThreadPoolExecutor(max_workers=config.workers)`.

- [ ] **Step 1: Write the failing tests**

  Inject a fake `run` callable: success returns `CompletedProcess` with stdout; a `subprocess.TimeoutExpired` raises `AgentError`; a nonzero exit raises `AgentError`. Test that `preflight` returns True when all worker calls succeed and False when one fails, and that `run_agent_calls` maps row index to output or `AgentError`.

- [ ] **Step 2: Run the tests to verify they fail**

  Run: `python3 -m unittest discover -s evals -v`
  Expected: FAIL.

- [ ] **Step 3: Implement in `evals/run_eval.py`**

  Use the fallback form only when `preflight` fails, starting one `opencode serve` process and passing its URL to each call. A run that stops because the preflight failed and the fallback cannot start returns exit status 2 from `main`.

- [ ] **Step 4: Run the tests to verify they pass**

  Run: `python3 -m unittest discover -s evals -v`
  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add evals/run_eval.py evals/test_run_eval.py
  git commit -m "feat: agent transport with preflight and serve/attach fallback"
  ```

### Task 6: Harbor sandbox leg

**Files:**
- Modify: `evals/run_eval.py`
- Modify: `evals/test_run_eval.py`

**Interfaces:**
- Consumes: `Config`, `Row`, `extract_command` from earlier tasks; the task layout from Task 2.
- Produces: `is_refusal(row) -> bool` (expected output starts with `! printf`), `refusal_prefix(expected: str) -> str` (the diagnostic prefix `Cannot generate a safe command:` or `Clarify:` from the expected command), `build_task_dir(workspace, row, fixture, command) -> path`, and `run_sandbox(config, jobs: list[(Row, str)]) -> dict[int, str]` with values `"yes"`, `"no"`, or `"error"`.

- [ ] **Step 1: Write the failing tests**

  - `test_is_refusal` and `test_refusal_prefix` on the three refusal rows in `docs/examples.json` and on a normal row.
  - `test_build_task_dir`: after building, the directory contains `task.toml` with `network_mode = "none"`, `instruction.md` equal to the request, `environment/Dockerfile` containing the fixture setup script, `tests/test.sh`, and `tests/command.txt` equal to the generated command.
  - `test_parse_rewards`: given a synthetic jobs directory with reward files, the parser maps task name to `"yes"` for reward 1 and `"no"` for reward 0, and `"error"` when the reward file is missing.
  - The verifier logic itself: `tests/test.sh` writes 1 when the command exits 0; for a refusal row it writes 1 only when the command exits 1 and stderr starts with the prefix. Test this by rendering `test.sh` for both row kinds and checking the branch with `bash -n` plus string checks.

- [ ] **Step 2: Run the tests to verify they fail**

  Run: `python3 -m unittest discover -s evals -v`
  Expected: FAIL.

- [ ] **Step 3: Implement in `evals/run_eval.py`**

  `build_task_dir` writes the four files per task, injecting the generated command into `tests/command.txt` and the refusal prefix into `tests/test.sh` when the row is a refusal. A fixture is an object `{"setup": "<shell run during the image build>"}` appended to the Dockerfile; a row without a fixture gets the bare `FROM ubuntu:24.04` image. `run_sandbox` writes all task directories under a run workspace, invokes the `harbor` CLI from Task 2 with `--n-concurrent config.workers`, then reads the reward files from the jobs directory.

- [ ] **Step 4: Run the tests to verify they pass**

  Run: `python3 -m unittest discover -s evals -v`
  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add evals/run_eval.py evals/test_run_eval.py
  git commit -m "feat: harbor sandbox leg with refusal-row verifier"
  ```

### Task 7: Judge leg

**Files:**
- Modify: `evals/run_eval.py`
- Modify: `evals/test_run_eval.py`

**Interfaces:**
- Consumes: `Config`, `Row`, `extract_command` from earlier tasks.
- Produces: `JudgeError` exception and `judge_row(config, row, generated, run=subprocess.run) -> str` returning `"yes"` or `"no"`, plus `run_judge(config, rows) -> dict[int, str | JudgeError]` over a thread pool.

- [ ] **Step 1: Write the failing tests**

  With an injected `run`: output `Yes` returns `"yes"`, `no` returns `"no"`, prose or an unrecognized answer raises `JudgeError`, a timeout raises `JudgeError`. Test that the judge prompt contains the request, the expected command, and the generated command, and that the call uses `opencode run --model JUDGE_MODEL` without `--agent bash`.

- [ ] **Step 2: Run the tests to verify they fail**

  Run: `python3 -m unittest discover -s evals -v`
  Expected: FAIL.

- [ ] **Step 3: Implement in `evals/run_eval.py`**

  One `opencode run` call per row that failed both exact match and sandbox, 30 second timeout, answer parsed with `extract_command`-style first-line logic and accepted only when the trimmed answer lowercases to `yes` or `no`.

- [ ] **Step 4: Run the tests to verify they pass**

  Run: `python3 -m unittest discover -s evals -v`
  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add evals/run_eval.py evals/test_run_eval.py
  git commit -m "feat: judge scorer for rows missing exact match and sandbox"
  ```

### Task 8: Scoring, report, results file, and exit status

**Files:**
- Modify: `evals/run_eval.py`
- Modify: `evals/test_run_eval.py`

**Interfaces:**
- Consumes: everything from Tasks 3 through 7.
- Produces: `score_row(...) -> "yes" | "no" | "error"` applying the pass rule (exact match, or sandbox, or judge), `render_report(...) -> str`, `write_results(results_dir, table) -> path` naming the file with the UTC timestamp, `compute_exit(passed, total, errors, min_pass_rate) -> int`, and the finished `main` that runs the six stages in spec order.

- [ ] **Step 1: Write the failing tests**

  - `test_pass_rule`: yes when only exact match says yes, when only sandbox says yes, when only judge says yes; no when all three say no.
  - `test_compute_exit`: no errors and rate at threshold gives 0, below gives 1, any error gives 2 even when the rate is fine, 2 wins over 1.
  - `test_render_report`: the report contains one line per example with category, the match, execution, and judge columns, the final yes or no, the expected command, and the generated command truncated to 80 characters, plus the overall pass rate and one line per category.
  - `test_candidate_dataset_bugs`: with `--repeat 3`, a row that fails all three repeats and is not an error row is listed as a candidate dataset bug; a row that errors in every repeat is not.
  - `test_write_results_name`: the file name matches the UTC timestamp pattern and the JSON contains the full table.

- [ ] **Step 2: Run the tests to verify they fail**

  Run: `python3 -m unittest discover -s evals -v`
  Expected: FAIL.

- [ ] **Step 3: Implement in `evals/run_eval.py`**

  `main` runs the stages in spec order: validate judge configuration, preflight, agent calls plus extraction plus exact match, sandbox, judge, then report, results file, exit. A stop before the first agent call writes no results file. When every row is an error, print no pass rate.

- [ ] **Step 4: Run the tests to verify they pass**

  Run: `python3 -m unittest discover -s evals -v`
  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add evals/run_eval.py evals/test_run_eval.py
  git commit -m "feat: scoring, report, results file, and exit statuses"
  ```

### Task 9: Smoke mode and the examples.md generator

**Files:**
- Modify: `evals/run_eval.py`
- Modify: `evals/test_run_eval.py`
- Modify: `docs/examples.md` (regenerated, never hand-edited)

**Interfaces:**
- Consumes: `Config`, `load_dataset` from Task 3.
- Produces: `--smoke` truncating the dataset to the first five rows, and `--render-docs` writing `docs/examples.md` from `docs/examples.json` and exiting 0.

- [ ] **Step 1: Write the failing tests**

  - `test_smoke_truncates`: a config with smoke True loads only the first five rows.
  - `test_render_docs_matches_file`: `render_examples_md(rows)` equals the current content of `docs/examples.md` byte for byte.

- [ ] **Step 2: Run the tests to verify they fail**

  Run: `python3 -m unittest discover -s evals -v`
  Expected: FAIL.

- [ ] **Step 3: Implement in `evals/run_eval.py`**

  `render_examples_md` reproduces the existing header prose and the `## <category>` sections with `Input:` and `Output:` lines in dataset order. If the test in step 1 shows a mismatch, adjust the generator until the bytes match, then regenerate `docs/examples.md` with `python3 evals/run_eval.py --render-docs`.

- [ ] **Step 4: Run the tests and the generator**

  Run: `python3 -m unittest discover -s evals -v` then `python3 evals/run_eval.py --render-docs`
  Expected: PASS, and `git diff docs/examples.md` is empty.

- [ ] **Step 5: Commit**

  ```bash
  git add evals/run_eval.py evals/test_run_eval.py docs/examples.md
  git commit -m "feat: smoke mode and generated docs/examples.md"
  ```

### Task 10: Seed evals/fixtures.json

**Files:**
- Modify: `evals/fixtures.json`

**Interfaces:**
- Consumes: `load_fixtures` from Task 3, `build_task_dir` from Task 6.
- Produces: a fixture entry for every example whose expected command needs machine state, keyed by the example's `input`, each fixture making the expected command exit 0 in the container.

- [ ] **Step 1: List the rows that need state**

  Run: `python3 -c "import json; [print(r['input'], '=>', r['output']) for r in json.load(open('docs/examples.json'))]"` and mark rows that reference a git repository, `/var/log/nginx`, `./src`, `./current`, a Docker daemon, or a network host.

- [ ] **Step 2: Write fixtures for those rows**

  Each entry is `{"<input>": {"setup": "<shell appended to the Dockerfile>"}}`, for example a git repository with a commit for git rows, a `./current` symlink, or a `/var/log/nginx` directory with restrictive permissions for the nginx row. Rows that need a Docker daemon or the public internet get no fixture; they pass through exact match or the judge.

- [ ] **Step 3: Verify with a smoke run**

  Run: `python3 evals/run_eval.py --smoke`
  Expected: the run completes, writes one file to `evals/results/`, and the report prints. Fix fixtures until every fixture-backed row that should exit 0 does.

- [ ] **Step 4: Commit**

  ```bash
  git add evals/fixtures.json
  git commit -m "feat: seed sandbox fixtures for state-dependent examples"
  ```

### Task 11: Add extraction steps 3 and 4 to askk.sh

**Files:**
- Modify: `askk.sh`

**Interfaces:**
- Consumes: the extraction contract in `docs/agent-spec.md` and the pinned behavior in `evals/test_run_eval.py` from Task 4.
- Produces: a wrapper that accepts exactly the same outputs as the runner.

- [ ] **Step 1: Verify the gap**

  Read `askk.sh` and confirm the awk pipeline keeps multi-line fence bodies and never runs `bash -n`, so the wrapper and the runner currently accept different outputs.

- [ ] **Step 2: Make the change**

  In `askk.sh`, after the existing extraction, reject the command when it spans more than one line and when `printf '%s' "$cmd" | bash -n` fails; on rejection print nothing to stdout and exit 1 (keep the stderr diagnostic).

- [ ] **Step 3: Verify by hand**

  Source `askk.sh` in a subshell with a stubbed `opencode` on `PATH` that prints a two-line fenced block, a syntax-error line, and `ls -la`; confirm the first two produce no command and status 1, and the last yields `ls -la`.

- [ ] **Step 4: Run the unit tests**

  Run: `python3 -m unittest discover -s evals -v`
  Expected: PASS, including `test_extract_matches_askk_awk`.

- [ ] **Step 5: Commit**

  ```bash
  git add askk.sh
  git commit -m "fix: askk.sh rejects multi-line and bash -n invalid commands"
  ```

### Task 12: Align the docs and add evals/README.md

**Files:**
- Modify: `docs/agent-spec.md`
- Create: `evals/README.md`

**Interfaces:**
- Produces: documentation that matches the code the evaluation measures.

- [ ] **Step 1: Resolve the tool permission contradiction**

  `docs/agent-spec.md` says the agent may run read-only inspection tools, but `.opencode/agents/bash.md` denies every tool. The evaluation measures `bash.md` as it is, so edit the Tool permissions section of `docs/agent-spec.md` to state that all tool permissions are denied in `bash.md`.

- [ ] **Step 2: Write `evals/README.md`**

  Usage of `python3 evals/run_eval.py`, the flags, the environment variables (`ASKK_MODEL`, `ASKK_JUDGE_MODEL`, and the provider credentials the CI job must set or every row is an error and the run exits 2), the exit statuses, `--smoke`, and how to run the unit tests.

- [ ] **Step 3: Commit**

  ```bash
  git add docs/agent-spec.md evals/README.md
  git commit -m "docs: align agent spec tool permissions and document the eval harness"
  ```
