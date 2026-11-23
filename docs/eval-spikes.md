# Eval spikes

Findings from the spikes in `evals/`. Each section records the command, the output, and the conclusion the runner relies on.

## Transport (`evals/spike_transport.py`)

Command: `ASKK_MODEL=melious/deepseek-v4.1-flash-1017 python3 evals/spike_transport.py --workers 8`

- Phase 1, 8 parallel `opencode run --agent bash --model MODEL "Show git status"` against the shared background server: 8/8 ok in about 2 seconds each. Parallel calls are safe here; no shared lock, port conflict, or serialization.
- Phase 2, one `opencode serve --hostname 127.0.0.1 --port 4799` plus 8 parallel `opencode run --server http://127.0.0.1:4799 --agent bash --model MODEL "Show git status"`: 8/8 ok in about 5.3 seconds each. The fallback works. In opencode v2.3.2 the flag is `--server URL`, not `--attach URL`.
- The spec default model `claude-agent/system.ai.claude-haiku-5-5` is unavailable in this environment (`Error: Model unavailable`). `ASKK_MODEL` must name an available model, for example `melious/deepseek-v4.1-flash-1017`. CI must set `ASKK_MODEL`, `ASKK_JUDGE_MODEL`, and the provider credentials, or every row is an error and the run exits 2.

Conclusion for `evals/run_eval.py`: preflight with `--workers` parallel `opencode run` calls; on failure switch to one `opencode serve` process plus `--server URL` on every call.
