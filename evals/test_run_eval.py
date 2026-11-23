import os
import sys
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
        source = open("askk.sh", encoding="utf-8").read()
        program = source.split("awk '", 1)[1].split("'", 1)[0]
        samples = [
            "prose\n```\nls -la\n```\nmore",
            "\n\npwd\n",
            "  ls -la  \n",
            "```\nfind . -name '*.py'\n| sort\n```",
            "one\ntwo\n",
        ]
        for sample in samples:
            with self.subTest(sample=sample):
                result = run_eval.select_command(sample)
                self.assertIsNotNone(result)
                proc = __import__("subprocess").run(
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


if __name__ == "__main__":
    unittest.main()
