import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_eval


class ConfigTest(unittest.TestCase):
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
        with mock.patch.dict(os.environ, {}, clear=True):
            config = run_eval.parse_args([])
        with self.assertRaises(run_eval.HarnessError):
            run_eval.validate_judge_config(config)

    def test_validate_judge_config_same_model(self):
        config = run_eval.parse_args([])
        config.model = "provider/model"
        config.judge_model = "provider/model"
        with self.assertRaises(run_eval.HarnessError):
            run_eval.validate_judge_config(config)

    def test_validate_judge_config_ok(self):
        config = run_eval.parse_args([])
        config.model = "provider/model"
        config.judge_model = "provider/judge"
        run_eval.validate_judge_config(config)
        config.judge_enabled = False
        config.judge_model = None
        run_eval.validate_judge_config(config)

    def test_load_dataset(self):
        rows = run_eval.load_dataset("docs/examples.json")
        self.assertEqual(len(rows), 100)
        self.assertEqual(rows[0].input, "List all files in this folder")


class ExtractionTest(unittest.TestCase):
    def test_extract_prefers_first_fenced_block(self):
        raw = "Here is the command:\n```bash\nls -la\n```\nUse it."
        self.assertEqual(run_eval.extract_command(raw), "ls -la")

    def test_extract_falls_back_to_first_non_empty_line(self):
        self.assertEqual(run_eval.extract_command("\n\npwd\n"), "pwd")

    def test_extract_trims(self):
        self.assertEqual(run_eval.extract_command("  ls -la  \n"), "ls -la")

    def test_extract_matches_askk_awk(self):
        with open("askk.sh", encoding="utf-8") as handle:
            source = handle.read()
        program = source.split("awk '", 1)[1].split("'", 1)[0]
        samples = [
            "prose\n```\nls -la\n```\nmore",
            "\n\npwd\n",
            "  ls -la  \n",
            "```\nfind . -name '*.py' | sort\n```",
            "one\ntwo\n",
        ]
        for sample in samples:
            with self.subTest(sample=sample):
                result = run_eval.select_command(sample)
                self.assertIsNotNone(result)
                proc = subprocess.run(
                    ["awk", program], input=sample, text=True, capture_output=True, check=True
                )
                self.assertEqual(result.strip(), proc.stdout.strip())

    def test_extract_rejects_multiline(self):
        self.assertIsNone(run_eval.extract_command("```\nls\npwd\n```"))

    def test_extract_rejects_syntax_error(self):
        self.assertIsNone(run_eval.extract_command("if true; then"))

    def test_extract_accepts_pipeline(self):
        self.assertEqual(
            run_eval.extract_command("find . -name '*.png' | wc -l"),
            "find . -name '*.png' | wc -l",
        )

    def test_exact_match(self):
        self.assertTrue(run_eval.exact_match("ls -la", "ls -la"))
        self.assertFalse(run_eval.exact_match("ls -la", "ls"))
        self.assertTrue(run_eval.exact_match("  ls -la ", "ls -la\n"))


class TransportTest(unittest.TestCase):
    def config(self):
        return run_eval.Config(model="provider/model")

    def test_call_agent_success(self):
        seen = []

        def fake_run(cmd, **kwargs):
            seen.append((cmd, kwargs))
            return subprocess.CompletedProcess(cmd, 0, "git status\n", "")

        output = run_eval.call_agent(self.config(), "Show git status", run=fake_run)
        self.assertEqual(output, "git status\n")
        self.assertEqual(seen[0][0][:2], ["opencode", "run"])
        self.assertIn("--agent", seen[0][0])
        self.assertEqual(seen[0][1]["timeout"], 30)

    def test_call_agent_timeout(self):
        def fake_run(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd, 30)

        with self.assertRaises(run_eval.AgentError):
            run_eval.call_agent(self.config(), "Show git status", run=fake_run)

    def test_call_agent_nonzero(self):
        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 1, "", "rate limit")

        with self.assertRaises(run_eval.AgentError):
            run_eval.call_agent(self.config(), "Show git status", run=fake_run)

    def test_preflight(self):
        def good(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 0, "git status", "")

        def bad(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 1, "", "nope")

        self.assertTrue(run_eval.preflight(self.config(), run=good))
        self.assertFalse(run_eval.preflight(self.config(), run=bad))

    def test_run_agent_calls_maps(self):
        rows = [
            run_eval.Row(0, "c", "one", "x"),
            run_eval.Row(1, "c", "two", "y"),
        ]

        def fake_run(cmd, **kwargs):
            if cmd[-1] == "two":
                raise subprocess.TimeoutExpired(cmd, 30)
            return subprocess.CompletedProcess(cmd, 0, "command", "")

        results = run_eval.run_agent_calls(self.config(), rows, run=fake_run)
        self.assertEqual(results[0], "command")
        self.assertIsInstance(results[1], run_eval.AgentError)

    def test_call_agent_uses_server_when_set(self):
        seen = {}

        def fake_run(cmd, **kwargs):
            seen["cmd"] = cmd
            return subprocess.CompletedProcess(cmd, 0, "git status\n", "")

        config = self.config()
        config.server_url = "http://127.0.0.1:1234"
        run_eval.call_agent(config, "Show git status", run=fake_run)
        self.assertIn("--server", seen["cmd"])
        self.assertIn("http://127.0.0.1:1234", seen["cmd"])
        self.assertNotIn("--attach", seen["cmd"])


class SandboxTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def rows(self):
        return run_eval.load_dataset("docs/examples.json")

    def test_is_refusal_and_prefix(self):
        rows = self.rows()
        refusals = [row for row in rows if run_eval.is_refusal(row)]
        self.assertEqual(len(refusals), 3)
        self.assertEqual(run_eval.refusal_prefix(refusals[0].output), "Cannot generate a safe command:")
        self.assertEqual(run_eval.refusal_prefix(refusals[1].output), "Clarify:")
        self.assertEqual(run_eval.refusal_prefix(refusals[2].output), "Cannot generate a safe command:")
        normal = next(row for row in rows if not run_eval.is_refusal(row))
        self.assertFalse(run_eval.is_refusal(normal))
        self.assertIsNone(run_eval.refusal_prefix(normal.output))

    def test_build_task_dir(self):
        row = run_eval.Row(7, "Files", "List the files", "ls -la")
        path = run_eval.build_task_dir(self.tmp.name, row, {"setup": "mkdir -p work"}, "ls -la")
        self.assertTrue(os.path.isdir(path))
        task_toml = open(os.path.join(path, "task.toml"), encoding="utf-8").read()
        self.assertIn('network_mode = "no-network"', task_toml)
        self.assertEqual(
            open(os.path.join(path, "instruction.md"), encoding="utf-8").read(),
            "List the files\n",
        )
        dockerfile = open(os.path.join(path, "environment", "Dockerfile"), encoding="utf-8").read()
        self.assertIn("mkdir -p work", dockerfile)
        self.assertEqual(
            open(os.path.join(path, "tests", "command.txt"), encoding="utf-8").read(),
            "ls -la\n",
        )
        verifier = open(os.path.join(path, "tests", "test.sh"), encoding="utf-8").read()
        self.assertTrue(verifier.startswith("#!/bin/bash"))
        self.assertTrue(os.access(os.path.join(path, "tests", "test.sh"), os.X_OK))

    def test_parse_rewards(self):
        jobs = os.path.join(self.tmp.name, "jobs")
        for name, reward in (("row-0__abc", "1"), ("row-1__def", "0")):
            path = os.path.join(jobs, "stamp", name, "verifier")
            os.makedirs(path)
            with open(os.path.join(path, "reward.txt"), "w", encoding="utf-8") as handle:
                handle.write(reward)
        result = run_eval.parse_rewards(jobs, ["row-0", "row-1", "row-2"])
        self.assertEqual(result, {"row-0": "yes", "row-1": "no", "row-2": "error"})

    def test_verifier_script_branches(self):
        normal = run_eval.Row(0, "c", "a", "true")
        refusal = run_eval.Row(1, "c", "b", "! printf 'Clarify: %s\\n' 'Which path?' >&2")
        normal_script = run_eval.verifier_script(normal)
        refusal_script = run_eval.verifier_script(refusal)
        self.assertIn("/logs/verifier/reward.txt", normal_script)
        self.assertIn("prefix=''", normal_script)
        self.assertIn("Clarify:", refusal_script)
        self.assertIn("head -c", refusal_script)
        for script in (normal_script, refusal_script):
            self.assertEqual(
                subprocess.run(["bash", "-n"], input=script, text=True).returncode,
                0,
            )


class JudgeTest(unittest.TestCase):
    def config(self):
        return run_eval.Config(model="provider/agent", judge_model="provider/judge")

    def row(self):
        return run_eval.Row(0, "c", "list the files", "ls -la")

    def test_judge_yes_and_no(self):
        def yes(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 0, "Yes\n", "")

        def no(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 0, "no\n", "")

        self.assertEqual(run_eval.judge_row(self.config(), self.row(), "ls", run=yes), "yes")
        self.assertEqual(run_eval.judge_row(self.config(), self.row(), "ls", run=no), "no")

    def test_judge_rejects_prose(self):
        def prose(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 0, "The command looks right.\n", "")

        with self.assertRaises(run_eval.JudgeError):
            run_eval.judge_row(self.config(), self.row(), "ls", run=prose)

    def test_judge_timeout(self):
        def slow(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd, 30)

        with self.assertRaises(run_eval.JudgeError):
            run_eval.judge_row(self.config(), self.row(), "ls", run=slow)

    def test_judge_prompt_and_command(self):
        seen = {}

        def fake(cmd, **kwargs):
            seen["cmd"] = cmd
            return subprocess.CompletedProcess(cmd, 0, "yes", "")

        run_eval.judge_row(self.config(), self.row(), "ls", run=fake)
        prompt = seen["cmd"][-1]
        self.assertIn("list the files", prompt)
        self.assertIn("ls -la", prompt)
        self.assertIn("Generated command:\nls", prompt)
        self.assertIn("--model", seen["cmd"])
        self.assertIn("provider/judge", seen["cmd"])
        self.assertNotIn("--agent", seen["cmd"])

    def test_run_judge_maps(self):
        rows = [
            (run_eval.Row(0, "c", "a", "ls"), "ls"),
            (run_eval.Row(1, "c", "b", "pwd"), "pwd"),
        ]

        def fake(cmd, **kwargs):
            if "Generated command:\npwd" in cmd[-1]:
                raise subprocess.TimeoutExpired(cmd, 30)
            return subprocess.CompletedProcess(cmd, 0, "yes", "")

        result = run_eval.run_judge(self.config(), rows, run=fake)
        self.assertEqual(result[0], "yes")
        self.assertIsInstance(result[1], run_eval.JudgeError)


class ScoringTest(unittest.TestCase):
    def item(self, **changes):
        item = {
            "index": 0, "repeat": 0, "category": "Git", "input": "show status",
            "output": "git status", "generated": "git status --short", "match": "no",
            "sandbox": "no", "judge": "yes", "final": "yes", "error": None,
        }
        item.update(changes)
        return item

    def test_score_row(self):
        self.assertEqual(run_eval.score_row("yes", "no", "no"), "yes")
        self.assertEqual(run_eval.score_row("no", "yes", "no"), "yes")
        self.assertEqual(run_eval.score_row("no", "no", "yes"), "yes")
        self.assertEqual(run_eval.score_row("no", "no", "no"), "no")
        self.assertEqual(run_eval.score_row("no", "error", "no"), "error")
        self.assertEqual(run_eval.score_row("yes", "error", "no"), "yes")

    def test_compute_exit(self):
        self.assertEqual(run_eval.compute_exit(10, 10, 0, 1.0), 0)
        self.assertEqual(run_eval.compute_exit(9, 10, 0, 1.0), 1)
        self.assertEqual(run_eval.compute_exit(10, 10, 1, 1.0), 2)
        self.assertEqual(run_eval.compute_exit(5, 10, 1, 0.0), 2)

    def test_render_report(self):
        table = [self.item(generated="x" * 100)]
        report = run_eval.render_report(table, 1)
        self.assertIn("Git", report)
        self.assertIn("match=no", report)
        self.assertIn("exec=no", report)
        self.assertIn("judge=yes", report)
        self.assertIn("final=yes", report)
        self.assertIn("git status", report)
        self.assertIn("x" * 77 + "...", report)
        self.assertNotIn("x" * 81, report)
        self.assertIn("pass rate: 1/1", report)
        self.assertIn("  Git: 1/1", report)

    def test_render_report_all_errors(self):
        report = run_eval.render_report([self.item(final="error", error="boom")], 1)
        self.assertNotIn("pass rate:", report)
        self.assertIn("every row is an error", report)
        self.assertNotIn("pass rate:", report)

    def test_candidate_dataset_bugs(self):
        table = []
        for repeat in range(3):
            table.append(self.item(index=0, repeat=repeat, input="bad row", final="no"))
            table.append(self.item(index=1, repeat=repeat, input="error row", final="error"))
        report = run_eval.render_report(table, 3)
        section = report.split("candidate dataset bugs", 1)[1]
        self.assertIn("bad row", section)
        self.assertNotIn("error row", section)

    def test_write_results_name(self):
        with tempfile.TemporaryDirectory() as directory:
            table = [self.item()]
            path = run_eval.write_results(directory, table)
            self.assertRegex(os.path.basename(path), r"^\d{8}T\d{6}Z\.json$")
            with open(path, encoding="utf-8") as handle:
                self.assertEqual(json.load(handle), table)


class MainTest(unittest.TestCase):
    def test_judge_config_error_writes_no_results(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.dict(os.environ, {"ASKK_JUDGE_MODEL": ""}, clear=False):
                code = run_eval.main(["--results-dir", directory])
            self.assertEqual(code, 2)
            self.assertEqual(os.listdir(directory), [])

    def test_preflight_failure_writes_no_results(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.dict(os.environ, {"ASKK_JUDGE_MODEL": "provider/judge"}, clear=False):
                with mock.patch("run_eval.start_transport", side_effect=run_eval.HarnessError("no transport")):
                    code = run_eval.main(["--results-dir", directory])
            self.assertEqual(code, 2)
            self.assertEqual(os.listdir(directory), [])

    def test_complete_run_writes_results(self):
        with tempfile.TemporaryDirectory() as directory:
            dataset = os.path.join(directory, "rows.json")
            with open(dataset, "w", encoding="utf-8") as handle:
                json.dump(
                    [
                        {"category": "A", "input": "first", "output": "ls"},
                        {"category": "A", "input": "second", "output": "pwd"},
                    ],
                    handle,
                )
            results = os.path.join(directory, "results")
            with mock.patch.dict(os.environ, {"ASKK_JUDGE_MODEL": "provider/judge"}, clear=False):
                with mock.patch("run_eval.start_transport", return_value=None):
                    with mock.patch("run_eval.run_agent_calls", return_value={0: "ls\n", 1: "echo hi\n"}):
                        with mock.patch("run_eval.run_sandbox", return_value={0: "no", 1: "yes"}):
                            with mock.patch("run_eval.run_judge", return_value={}):
                                code = run_eval.main(["--dataset", dataset, "--results-dir", results])
            self.assertEqual(code, 0)
            files = os.listdir(results)
            self.assertEqual(len(files), 1)
            table = json.load(open(os.path.join(results, files[0]), encoding="utf-8"))
            self.assertEqual([item["final"] for item in table], ["yes", "yes"])
            self.assertEqual({item["match"] for item in table}, {"yes", "no"})

    def test_any_error_exits_2(self):
        with tempfile.TemporaryDirectory() as directory:
            dataset = os.path.join(directory, "rows.json")
            with open(dataset, "w", encoding="utf-8") as handle:
                json.dump([{"category": "A", "input": "first", "output": "ls"}], handle)
            results = os.path.join(directory, "results")
            with mock.patch.dict(os.environ, {"ASKK_JUDGE_MODEL": "provider/judge"}, clear=False):
                with mock.patch("run_eval.start_transport", return_value=None):
                    with mock.patch("run_eval.run_agent_calls", return_value={0: run_eval.AgentError("boom")}):
                        code = run_eval.main(["--dataset", dataset, "--results-dir", results])
            self.assertEqual(code, 2)


class DocsTest(unittest.TestCase):
    def test_smoke_truncates(self):
        with mock.patch.dict(os.environ, {"ASKK_JUDGE_MODEL": "provider/judge"}, clear=False):
            config = run_eval.parse_args(["--smoke"])
            rows = run_eval.load_rows(config)
        self.assertEqual(len(rows), 5)

    def test_render_docs_matches_file(self):
        rows = run_eval.load_dataset("docs/examples.json")
        expected = open("docs/examples.md", encoding="utf-8").read()
        self.assertEqual(run_eval.render_examples_md(rows), expected)

    def test_render_docs_flag(self):
        before = open("docs/examples.md", encoding="utf-8").read()
        self.assertEqual(run_eval.main(["--render-docs"]), 0)
        self.assertEqual(open("docs/examples.md", encoding="utf-8").read(), before)


if __name__ == "__main__":
    unittest.main()
