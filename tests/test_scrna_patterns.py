"""
test_scrna_patterns.py - Tests for scRNA-seq error patterns.
Mirrors the existing test structure in BioOps Guardian.
"""

import unittest
from src.scrna_patterns import SCRNA_PATTERNS


def match_pattern(pattern_id, log_text):
    """Helper: returns True if any regex in the pattern matches the log text."""
    for pattern in SCRNA_PATTERNS:
        if pattern["id"] == pattern_id:
            return any(r.search(log_text) for r in pattern["patterns"])
    return False


class TestScrnaPatterns(unittest.TestCase):

    def test_starsolo_memory_exit_137(self):
        log = "STARsolo terminated exit code 137 killed by system"
        self.assertTrue(match_pattern("starsolo_memory", log))

    def test_starsolo_memory_cannot_allocate(self):
        log = "STAR cannot allocate memory for genome index"
        self.assertTrue(match_pattern("starsolo_memory", log))

    def test_barcode_whitelist_missing(self):
        log = "soloCBwhitelist file not found: /data/whitelist_10xv3.txt"
        self.assertTrue(match_pattern("barcode_whitelist_missing", log))

    def test_barcode_whitelist_cannot_open(self):
        log = "CB whitelist cannot open file at specified path"
        self.assertTrue(match_pattern("barcode_whitelist_missing", log))

    def test_wrong_chemistry(self):
        log = "chemistry 10xv2 not recognized for this library type"
        self.assertTrue(match_pattern("wrong_chemistry", log))

    def test_empty_cell_output(self):
        log = "0 cells detected after filtering barcode matrix"
        self.assertTrue(match_pattern("empty_cell_output", log))

    def test_cellranger_fastq_naming(self):
        log = "_R1_001.fastq.gz not found for sample S1"
        self.assertTrue(match_pattern("cellranger_fastq_naming", log))

    def test_kallisto_empty_bus(self):
        log = "bus file is empty — 0 records written"
        self.assertTrue(match_pattern("kallisto_empty_bus", log))

    def test_anndata_version_mismatch(self):
        log = "anndata version incompatible — file was written by newer version"
        self.assertTrue(match_pattern("anndata_version_mismatch", log))

    def test_scrna_genome_mismatch(self):
        log = "chromosome chr1 not found in GTF annotation file"
        self.assertTrue(match_pattern("scrna_genome_mismatch", log))

    def test_no_false_positive_clean_log(self):
        """A clean bulk RNA-seq log should not match any scRNA-seq pattern."""
        log = "Pipeline completed successfully. 95% reads mapped."
        for pattern in SCRNA_PATTERNS:
            matched = any(r.search(log) for r in pattern["patterns"])
            self.assertFalse(matched, f"False positive: {pattern['id']}")

    def test_all_patterns_have_required_keys(self):
        """Every pattern must have all required fields."""
        required = {"id", "label", "patterns", "severity", "icon", "cause", "fix", "command"}
        for pattern in SCRNA_PATTERNS:
            for key in required:
                self.assertIn(key, pattern, f"Missing '{key}' in pattern '{pattern.get('id')}'")

    def test_all_patterns_have_compiled_regex(self):
        """Every pattern's regex list must be compiled re objects."""
        import re
        for pattern in SCRNA_PATTERNS:
            for r in pattern["patterns"]:
                self.assertIsInstance(r, type(re.compile("")),
                    f"Pattern '{pattern['id']}' has uncompiled regex")


if __name__ == "__main__":
    unittest.main()
