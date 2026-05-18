"""Tests for src/log_parser.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import unittest
from src.log_parser import parse_nextflow_log


class TestLogParser(unittest.TestCase):

    def test_empty_log(self):
        result = parse_nextflow_log("")
        self.assertEqual(result["detected"], [])
        self.assertEqual(result["total_processes"], 0)

    def test_clean_log(self):
        log = "N E X T F L O W  ~  version 23.10.0\nAll done."
        result = parse_nextflow_log(log)
        self.assertEqual(result["detected"], [])

    def test_memory_exceeded(self):
        log = "Process requirement exceeds available memory -- req: 36 GB; avail: 15.8 GB"
        result = parse_nextflow_log(log)
        ids = [d["id"] for d in result["detected"]]
        self.assertIn("memory_exceeded", ids)

    def test_missing_file(self):
        log = "No such file or directory: /data/genome.fa"
        result = parse_nextflow_log(log)
        ids = [d["id"] for d in result["detected"]]
        self.assertIn("missing_file", ids)

    def test_container_issue(self):
        log = "FATAL: container creation failed: mount error"
        result = parse_nextflow_log(log)
        ids = [d["id"] for d in result["detected"]]
        self.assertIn("container_issue", ids)

    def test_process_extraction(self):
        log = "[2a/f8c3b1] process > FASTQC (SAMPLE_01) [100%] 6 of 6\n"
        result = parse_nextflow_log(log)
        self.assertEqual(len(result["processes"]), 1)
        self.assertEqual(result["processes"][0]["name"], "FASTQC (SAMPLE_01)")
        self.assertTrue(result["processes"][0]["done"])

    def test_metadata_extraction(self):
        log = (
            "N E X T F L O W  ~  version 23.10.0\n"
            "Launching `nf-core/rnaseq` [happy_darwin] DSL2 - revision: 3.12.0\n"
            "Work dir: /home/user/work\n"
        )
        result = parse_nextflow_log(log)
        self.assertEqual(result["meta"]["nf_version"], "23.10.0")
        self.assertEqual(result["meta"]["pipeline"], "nf-core/rnaseq")
        self.assertEqual(result["meta"]["revision"], "3.12.0")

    def test_confidence_scales_with_matches(self):
        log = (
            "Process requirement exceeds available memory\n"
            "java.lang.OutOfMemoryError: GC overhead\n"
            "Cannot allocate memory\n"
        )
        result = parse_nextflow_log(log)
        mem = [d for d in result["detected"] if d["id"] == "memory_exceeded"][0]
        self.assertGreater(mem["confidence"], 0.8)


if __name__ == "__main__":
    unittest.main()
