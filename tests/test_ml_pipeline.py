"""Tests for src/synthetic_data.py, src/feature_extractor.py, and src/ml_classifier.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import unittest
from src.synthetic_data import generate_single_log, generate_dataset
from src.feature_extractor import extract_features, get_feature_names


class TestSyntheticData(unittest.TestCase):

    CATEGORIES = [
        "memory_exceeded", "missing_file", "container_issue", "reference_index",
        "permission_issue", "failed_process", "invalid_parameter", "disk_space", "clean",
    ]

    def test_generate_all_categories(self):
        for cat in self.CATEGORIES:
            log = generate_single_log(cat, seed=1)
            self.assertEqual(log["label"], cat)
            self.assertGreater(len(log["text"]), 50)

    def test_generate_dataset_counts(self):
        ds = generate_dataset(n_per_category=5, include_clean=True, seed=1)
        counts = {}
        for item in ds:
            counts[item["label"]] = counts.get(item["label"], 0) + 1
        for cat in self.CATEGORIES:
            self.assertEqual(counts.get(cat, 0), 5, f"Expected 5 for {cat}")

    def test_logs_have_nf_header(self):
        for cat in self.CATEGORIES:
            log = generate_single_log(cat, seed=42)
            self.assertIn("N E X T F L O W", log["text"])

    def test_reproducibility(self):
        a = generate_single_log("memory_exceeded", seed=123)
        b = generate_single_log("memory_exceeded", seed=123)
        # Same seed produces same label and same pipeline metadata
        self.assertEqual(a["label"], b["label"])
        self.assertEqual(a["meta"]["pipeline"], b["meta"]["pipeline"])

    def test_different_seeds_different_logs(self):
        a = generate_single_log("memory_exceeded", seed=1)
        b = generate_single_log("memory_exceeded", seed=2)
        self.assertNotEqual(a["text"], b["text"])


class TestFeatureExtractor(unittest.TestCase):

    def test_memory_features(self):
        text = "Process requirement exceeds available memory -- req: 36 GB; avail: 15.8 GB"
        feats = extract_features(text)
        self.assertAlmostEqual(feats["memory_requested_gb"], 36.0)
        self.assertAlmostEqual(feats["memory_available_gb"], 15.8)
        self.assertGreater(feats["memory_ratio"], 2.0)

    def test_exit_code_extraction(self):
        text = "Command exit status: 137"
        feats = extract_features(text)
        self.assertEqual(feats["exit_code"], 137)
        self.assertEqual(feats["exit_is_137"], 1)

    def test_regex_flags(self):
        text = "Permission denied: /data/file\nEACCES"
        feats = extract_features(text)
        self.assertGreater(feats["regex_permission_issue"], 0)
        self.assertEqual(feats["has_permission"], 1)

    def test_empty_log(self):
        feats = extract_features("")
        self.assertEqual(feats["exit_code"], 0)
        self.assertEqual(feats["n_processes"], 0)

    def test_feature_names_match(self):
        names = get_feature_names()
        feats = extract_features("test")
        for name in names:
            self.assertIn(name, feats, f"Missing feature: {name}")

    def test_process_counting(self):
        text = (
            "[2a/f8c3b1] process > FASTQC (S1) [100%] 6 of 6\n"
            "[5d/a12e89] process > TRIM (S1)    [  0%] 0 of 6\n"
        )
        feats = extract_features(text)
        self.assertEqual(feats["n_processes"], 2)
        self.assertEqual(feats["n_completed"], 1)
        self.assertEqual(feats["n_failed"], 1)


if __name__ == "__main__":
    unittest.main()
