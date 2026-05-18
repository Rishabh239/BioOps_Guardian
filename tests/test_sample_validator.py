"""Tests for src/sample_validator.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import unittest
from src.sample_validator import validate_sample_sheet


class TestSampleValidator(unittest.TestCase):

    GOOD_SHEET = (
        "sample,fastq_1,fastq_2,strandedness\n"
        "S1,/d/S1_R1.fastq.gz,/d/S1_R2.fastq.gz,reverse\n"
    )

    def test_valid_sheet(self):
        result = validate_sample_sheet(self.GOOD_SHEET)
        self.assertEqual(len(result["issues"]), 0)

    def test_empty_sheet(self):
        result = validate_sample_sheet("sample")
        self.assertTrue(any(i["type"] == "critical" for i in result["issues"]))

    def test_missing_columns(self):
        sheet = "sample,fastq_1\nS1,/d/f.fastq.gz\n"
        result = validate_sample_sheet(sheet)
        msgs = " ".join(i["message"] for i in result["issues"])
        self.assertIn("Missing required columns", msgs)

    def test_duplicate_sample_id(self):
        sheet = (
            "sample,fastq_1,fastq_2,strandedness\n"
            "S1,/d/S1_R1.fastq.gz,/d/S1_R2.fastq.gz,reverse\n"
            "S1,/d/S1b_R1.fastq.gz,/d/S1b_R2.fastq.gz,reverse\n"
        )
        result = validate_sample_sheet(sheet)
        msgs = " ".join(i["message"] for i in result["issues"])
        self.assertIn("Duplicate", msgs)

    def test_invalid_strandedness(self):
        sheet = (
            "sample,fastq_1,fastq_2,strandedness\n"
            "S1,/d/S1_R1.fastq.gz,/d/S1_R2.fastq.gz,banana\n"
        )
        result = validate_sample_sheet(sheet)
        self.assertTrue(any("strandedness" in i["message"].lower() for i in result["issues"]))

    def test_single_end_detected(self):
        sheet = (
            "sample,fastq_1,fastq_2,strandedness\n"
            "S1,/d/S1_R1.fastq.gz,,reverse\n"
        )
        result = validate_sample_sheet(sheet)
        self.assertEqual(result["summary"]["single_end"], 1)

    def test_bad_extension(self):
        sheet = (
            "sample,fastq_1,fastq_2,strandedness\n"
            "S1,/d/S1_R1.bam,/d/S1_R2.bam,reverse\n"
        )
        result = validate_sample_sheet(sheet)
        self.assertTrue(any("fastq.gz" in i["message"] for i in result["issues"]))

    def test_paired_end_naming_mismatch(self):
        sheet = (
            "sample,fastq_1,fastq_2,strandedness\n"
            "S1,/d/sampleA_R1.fastq.gz,/d/sampleB_R2.fastq.gz,reverse\n"
        )
        result = validate_sample_sheet(sheet)
        msgs = " ".join(i["message"] for i in result["issues"])
        self.assertIn("naming convention", msgs)


if __name__ == "__main__":
    unittest.main()
