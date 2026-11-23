# Eval spikes

Findings from the spikes in `evals/`. Each section records the command, the output, and the conclusion the runner relies on.

## Transport (`evals/spike_transport.py`)

Command: `ASKK_MODEL=melious/deepseek-v4.1-flash-1017 python3 evals/spike_transport.py --workers 8`

- Phase 1, 8 parallel `opencode run --agent bash --model MODEL "Show git status"` against the shared background server: 8/8 ok in about 2 seconds each. Parallel calls are safe here; no shared lock, port conflict, or serialization.
- Phase 2, one `opencode serve --hostname 127.0.0.1 --port 4799` plus 8 parallel `opencode run --server http://127.0.0.1:4799 --agent bash --model MODEL "Show git status"`: 8/8 ok in about 5.3 seconds each. The fallback works. In opencode v2.3.2 the flag is `--server URL`, not `--attach URL`.
- The spec default model `claude-agent/system.ai.claude-haiku-5-5` is unavailable in this environment (`Error: Model unavailable`). `ASKK_MODEL` must name an available model, for example `melious/deepseek-v4.1-flash-1017`. CI must set `ASKK_MODEL`, `ASKK_JUDGE_MODEL`, and the provider credentials, or every row is an error and the run exits 2.

Conclusion for `evals/run_eval.py`: preflight with `--workers` parallel `opencode run` calls; on failure switch to one `opencode serve` process plus `--server URL` on every call.

## Harbor task with an injected command (`evals/spike_harbor.py`)

Command: `python3 evals/spike_harbor.py` (Harbor 0.23.0, Docker 29.1.3)

- The script builds three task directories and runs `harbor run -p <tasks> --agent nop -n 3 -o <jobs> --yes`. A directory of task directories is a valid dataset when each child holds `task.toml`, `instruction.md`, `environment/Dockerfile`, and `tests/test.sh`. One job runs all three in parallel.
- Harbor requires `[environment] network_mode = "no-network"`. The value `"none"` fails task validation and Harbor then reports `Either datasets or tasks must be provided`.
- `--agent nop` skips the agent phase. The verifier in `tests/test.sh` runs the command from `tests/command.txt`; no model call happens in the container.
- The verifier writes `/logs/verifier/reward.txt` in the container. On the host the reward lands at `<jobs>/<timestamp>/<task>__<suffix>/verifier/reward.txt`. The trial result at `<jobs>/<timestamp>/<task>__<suffix>/result.json` carries `verifier_result.rewards.reward`.
- Result: rewards 1, 0, and 1 for commands `true`, `false`, and the refusal command that exits 1 with a `Clarify:` diagnostic. The refusal rule needs the exit 1 and stderr prefix check; exit 0 alone is not enough.
- Conclusion for `evals/run_eval.py`: build one task directory per example, run one `harbor run` with `--n-concurrent`, and read each reward file. Ignore the Harbor process exit status and parse reward files instead, because a container that writes root-owned job files can make Harbor's final cleanup fail after the rewards exist.
