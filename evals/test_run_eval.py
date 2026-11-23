import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import run_eval


class SkeletonTests(unittest.TestCase):
    def test_parse_args_defaults(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            config = run_eval.parse_args([])
        self.assertEqual(config.workers, 8)
        self.assertEqual(config.repeat, 1)
        self.assertEqual(config.min_pass_rate, 1.0)
        self.assertTrue(config.judge_enabled)
        self.assertEqual(config.model, "claude-agent/system.ai.claude-haiku-5-5")
        self.assertEqual(config.dataset_path, "docs/examples.json")

    def test_validate_judge_config_unset(self):
        config = run_eval.parse_args([])
        config.judge_enabled = True
        config.judge_model = None
        with self.assertRaises(run_eval.HarnessError):
            run_eval.validate_judge_config(config)

    def test_validate_judge_config_same_model(self):
        config = run_eval.parse_args([])
        config.judge_enabled = True
        config.model = "provider/model"
        config.judge_model = "provider/model"
        with self.assertRaises(run_eval.HarnessError):
            run_eval.validate_judge_config(config)

    def test_validate_judge_config_ok(self):
        config = run_eval.parse_args([])
        config.judge_enabled = True
        config.model = "provider/agent"
        config.judge_model = "provider/judge"
        run_eval.validate_judge_config(config)
        config.judge_enabled = False
        config.judge_model = None
        run_eval.validate_judge_config(config)

    def test_load_dataset(self):
        rows = run_eval.load_dataset("docs/examples.json")
        self.assertEqual(len(rows), 100)
        self.assertEqual(rows[0].input, "List all files in this folder")


class TransportTest(unittest.TestCase):
    def config(self, **changes):
        config = run_eval.Config(dataset_path="docs/examples.json")
        for key, value in changes.items():
            setattr(config, key, value)
        return config

    def test_call_agent_success(self):
        def run(cmd, **kwargs):
            self.assertEqual(cmd[:5], ["opencode", "run", "--agent", "bash", "--model"])
            self.assertEqual(cmd[-1], "Show git status")
            self.assertEqual(kwargs["timeout"], 30)
            return __import__("subprocess").CompletedProcess(cmd, 0, "git status\n", "")

        self.assertEqual(run_eval.call_agent(self.config(), "Show git status", run), "git status\n")

    def test_call_agent_timeout(self):
        def run(cmd, **kwargs):
            raise __import__("subprocess").TimeoutExpired(cmd, 30)

        with self.assertRaises(run_eval.AgentError):
            run_eval.call_agent(self.config(), "Show git status", run)

    def test_call_agent_nonzero(self):
        def run(cmd, **kwargs):
            return __import__("subprocess").CompletedProcess(cmd, 1, "", "boom")

        with self.assertRaises(run_eval.AgentError):
            run_eval.call_agent(self.config(), "Show git status", run)

    def test_preflight_all_ok(self):
        def run(cmd, **kwargs):
            return __import__("subprocess").CompletedProcess(cmd, 0, "git status\n", "")

        self.assertTrue(run_eval.preflight(self.config(workers=3), run))

    def test_preflight_one_fails(self):
        calls = {"n": 0}

        def run(cmd, **kwargs):
            calls["n"] += 1
            if calls["n"] == 2:
                return __import__("subprocess").CompletedProcess(cmd, 1, "", "boom")
            return __import__("subprocess").CompletedProcess(cmd, 0, "git status\n", "")

        self.assertFalse(run_eval.preflight(self.config(workers=3), run))

    def test_run_agent_calls_maps_output_and_error(self):
        def run(cmd, **kwargs):
            if cmd[-1] == "bad":
                return __import__("subprocess").CompletedProcess(cmd, 1, "", "boom")
            return __import__("subprocess").CompletedProcess(cmd, 0, cmd[-1] + "\n", "")

        rows = [
            run_eval.Row(0, "a", "one", "one"),
            run_eval.Row(1, "a", "bad", "bad"),
        ]
        result = run_eval.run_agent_calls(self.config(workers=2), rows, run=run)
        self.assertEqual(result[(0, 0)], "one\n")
        self.assertIsInstance(result[(1, 0)], run_eval.AgentError)

    def test_call_agent_uses_server_when_set(self):
        seen = {}

        def run(cmd, **kwargs):
            seen["cmd"] = cmd
            return __import__("subprocess").CompletedProcess(cmd, 0, "git status\n", "")

        config = self.config(server_url="http://127.0.0.1:1234")
        run_eval.call_agent(config, "Show git status", run)
        self.assertIn("--server", seen["cmd"])
        self.assertIn("http://127.0.0.1:1234", seen["cmd"])
        self.assertNotIn("--attach", seen["cmd"])


class TransportTest(unittest.TestCase):
    def config(self):
        return run_eval.Config(model="provider/model")

    def test_call_agent_success(self):
        seen = []

        def fake_run(cmd, **kwargs):
            seen.append((cmd, kwargs))
            return __import__("subprocess").CompletedProcess(cmd, 0, "git status\n", "")

        output = run_eval.call_agent(self.config(), "Show git status", run=fake_run)
        self.assertEqual(output, "git status\n")
        self.assertEqual(seen[0][0][:2], ["opencode", "run"])
        self.assertIn("--agent", seen[0][0])
        self.assertEqual(seen[0][1]["timeout"], 30)

    def test_call_agent_timeout(self):
        def fake_run(cmd, **kwargs):
            raise __import__("subprocess").TimeoutExpired(cmd, 30)

        with self.assertRaises(run_eval.AgentError):
            run_eval.call_agent(self.config(), "Show git status", run=fake_run)

    def test_call_agent_nonzero(self):
        def fake_run(cmd, **kwargs):
            return __import__("subprocess").CompletedProcess(cmd, 1, "", "rate limit")

        with self.assertRaises(run_eval.AgentError):
            run_eval.call_agent(self.config(), "Show git status", run=fake_run)

    def test_preflight(self):
        def good(cmd, **kwargs):
            return __import__("subprocess").CompletedProcess(cmd, 0, "git status", "")

        def bad(cmd, **kwargs):
            return __import__("subprocess").CompletedProcess(cmd, 1, "", "nope")

        self.assertTrue(run_eval.preflight(self.config(), run=good))
        self.assertFalse(run_eval.preflight(self.config(), run=bad))

    def test_run_agent_calls_maps(self):
        rows = [
            run_eval.Row(0, "c", "one", "x"),
            run_eval.Row(1, "c", "two", "y"),
        ]

        def fake_run(cmd, **kwargs):
            request = cmd[-1]
            if request == "two":
                raise __import__("subprocess").TimeoutExpired(cmd, 30)
            return __import__("subprocess").CompletedProcess(cmd, 0, "command", "")

        results = run_eval.run_agent_calls(self.config(), rows, run=fake_run)
        self.assertEqual(results[0], "command")
        self.assertIsInstance(results[1], run_eval.AgentError)


if __name__ == "__main__":
    unittest.main()
