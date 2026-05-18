"""Tests for src/preflight.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import unittest
from src.preflight import (
    run_preflight, check_samplesheet, check_config,
    check_memory_sufficiency, _parse_config,
)


class TestConfigParsing(unittest.TestCase):

    def test_parse_memory(self):
        config = "params { max_memory = '16.GB' }"
        settings = _parse_config(config)
        self.assertEqual(settings["max_memory"], 16.0)

    def test_parse_cpus(self):
        config = "params { max_cpus = 8 }"
        settings = _parse_config(config)
        self.assertEqual(settings["max_cpus"], 8)

    def test_parse_genome(self):
        config = "params { genome = 'GRCh38' }"
        settings = _parse_config(config)
        self.assertEqual(settings["genome"], "GRCh38")

    def test_parse_docker(self):
        config = "docker { enabled = true }"
        settings = _parse_config(config)
        self.assertEqual(settings["container_engine"], "docker")

    def test_parse_conda(self):
        config = "conda { enabled = true }"
        settings = _parse_config(config)
        self.assertEqual(settings["container_engine"], "conda")

    def test_parse_fasta(self):
        config = "params { fasta = '/data/genome.fa' }"
        settings = _parse_config(config)
        self.assertEqual(settings["fasta"], "/data/genome.fa")


class TestPreflightChecks(unittest.TestCase):

    GOOD_SHEET = (
        "sample,fastq_1,fastq_2,strandedness\n"
        "S1,/d/S1_R1.fastq.gz,/d/S1_R2.fastq.gz,reverse\n"
    )

    def test_samplesheet_valid(self):
        checks, summary = check_samplesheet(samplesheet_text=self.GOOD_SHEET)
        statuses = [c["status"] for c in checks]
        # Should have at least one pass (structure valid)
        self.assertIn("pass", statuses)

    def test_samplesheet_missing_columns(self):
        bad_sheet = "sample,fastq_1\nS1,/d/f.fastq.gz\n"
        checks, summary = check_samplesheet(samplesheet_text=bad_sheet)
        messages = " ".join(c["message"] for c in checks)
        self.assertIn("Missing required columns", messages)

    def test_config_low_memory_warning(self):
        config = "params { max_memory = '2.GB' }"
        checks, settings = check_config(config_text=config)
        statuses = [c["status"] for c in checks]
        self.assertIn("warn", statuses)

    def test_config_brace_mismatch(self):
        config = "params { max_memory = '16.GB'"  # missing closing brace
        checks, settings = check_config(config_text=config)
        fail_msgs = [c["message"] for c in checks if c["status"] == "fail"]
        self.assertTrue(any("brace" in m.lower() for m in fail_msgs))

    def test_memory_sufficiency_fail(self):
        settings = {"genome": "GRCh38", "max_memory": 8}
        checks = check_memory_sufficiency(settings)
        statuses = [c["status"] for c in checks]
        self.assertIn("fail", statuses)  # 8GB < 32GB needed for STAR on GRCh38

    def test_memory_sufficiency_pass(self):
        settings = {"genome": "GRCh38", "max_memory": 64}
        checks = check_memory_sufficiency(settings)
        statuses = [c["status"] for c in checks]
        self.assertIn("pass", statuses)

    def test_run_preflight_with_sheet_only(self):
        result = run_preflight(samplesheet_text=self.GOOD_SHEET)
        self.assertIn("verdict", result)
        self.assertIn("checks", result)
        self.assertGreater(len(result["checks"]), 0)

    def test_run_preflight_with_config_only(self):
        config = "params { max_memory = '32.GB'\n max_cpus = 16\n genome = 'GRCh38' }\ndocker { enabled = true }"
        result = run_preflight(config_text=config)
        self.assertIn("verdict", result)
        self.assertEqual(result["config_settings"]["max_memory"], 32.0)

    def test_run_preflight_full(self):
        config = "params { max_memory = '32.GB'\n genome = 'GRCh38' }\ndocker { enabled = true }"
        result = run_preflight(
            samplesheet_text=self.GOOD_SHEET,
            config_text=config,
        )
        self.assertIn("verdict", result)
        self.assertGreater(result["summary"]["total"], 3)


if __name__ == "__main__":
    unittest.main()
