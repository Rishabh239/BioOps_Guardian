"""
feature_extractor.py - Extract structured features from Nextflow logs for ML.

Combines three feature types:
  1. Structured fields: exit code, memory values, process counts, etc.
  2. Regex pattern flags: binary indicators for each of the 8 error patterns
  3. Text features: TF-IDF on the raw log text (handled in ml_classifier.py)

Usage:
    from src.feature_extractor import extract_features
    features = extract_features(log_text)
"""

import re
from src.patterns import ERROR_PATTERNS
from src.scrna_patterns import SCRNA_PATTERNS

ALL_PATTERNS = ERROR_PATTERNS + SCRNA_PATTERNS


def extract_features(text: str) -> dict:
    """Extract structured features from a Nextflow log."""
    features = {}

    # ── Exit code ────────────────────────────────────────────────
    exit_match = re.search(r"Command exit status:\s*(\S+)", text, re.I)
    if exit_match and exit_match.group(1) != "-":
        try:
            features["exit_code"] = int(exit_match.group(1))
        except ValueError:
            features["exit_code"] = -1
    else:
        features["exit_code"] = 0

    # ── Memory values (GB) ───────────────────────────────────────
    mem_req = re.search(r"req:\s*([\d.]+)\s*GB", text, re.I)
    mem_avail = re.search(r"avail:\s*([\d.]+)\s*GB", text, re.I)
    features["memory_requested_gb"] = float(mem_req.group(1)) if mem_req else 0.0
    features["memory_available_gb"] = float(mem_avail.group(1)) if mem_avail else 0.0
    features["memory_ratio"] = (
        features["memory_requested_gb"] / features["memory_available_gb"]
        if features["memory_available_gb"] > 0
        else 0.0
    )

    # ── Process progress ─────────────────────────────────────────
    proc_re = re.compile(
        r"\[([a-f0-9]{2}/[a-f0-9]{6})\]\s+process\s*>.*"
        r"\[(\s*\d+%)\]\s*(\d+)\s+of\s+(\d+)",
        re.I,
    )
    procs = proc_re.findall(text)
    features["n_processes"] = len(procs)
    features["n_completed"] = sum(1 for _, pct, _, _ in procs if pct.strip() == "100%")
    features["n_failed"] = features["n_processes"] - features["n_completed"]
    features["completion_ratio"] = (
        features["n_completed"] / features["n_processes"]
        if features["n_processes"] > 0
        else 1.0
    )

    # ── Log length / structure ───────────────────────────────────
    lines = text.split("\n")
    features["n_lines"] = len(lines)
    features["n_error_lines"] = sum(1 for l in lines if re.search(r"error|fatal|exception", l, re.I))
    features["n_warning_lines"] = sum(1 for l in lines if re.search(r"warn", l, re.I))
    features["error_density"] = features["n_error_lines"] / max(features["n_lines"], 1)

    # ── Has specific markers ─────────────────────────────────────
    features["has_stack_trace"] = int(bool(re.search(r"^\s+at\s+", text, re.M)))
    features["has_oom"] = int(bool(re.search(r"OutOfMemoryError|oom-kill|SIGKILL", text, re.I)))
    features["has_permission"] = int(bool(re.search(r"Permission denied|EACCES", text, re.I)))
    features["has_disk"] = int(bool(re.search(r"No space left|ENOSPC|Disk quota", text, re.I)))
    features["has_container"] = int(bool(re.search(r"docker|singularity|container|OCI|conda|mamba|Failed to create.*environment", text, re.I)))
    features["has_index"] = int(bool(re.search(r"genome index|genomeGenerate|faidx|\.fai", text, re.I)))
    features["has_schema_error"] = int(bool(re.search(r"Schema validation|Unknown.*parameter", text, re.I)))
    features["has_pipeline_failed"] = int(bool(re.search(r"Pipeline completed with errors|Pipeline failed|Session aborted", text, re.I)))
    features["has_conda_error"] = int(bool(re.search(r"Failed to create Conda environment|conda.*error|CondaError|mamba.*error", text, re.I)))

    # ── Exit code categories (one-hot) ───────────────────────────
    ec = features["exit_code"]
    features["exit_is_137"] = int(ec == 137)  # OOM kill
    features["exit_is_1"] = int(ec == 1)  # generic error
    features["exit_is_127"] = int(ec == 127)  # command not found
    features["exit_is_126"] = int(ec == 126)  # permission / not executable
    features["exit_is_139"] = int(ec == 139)  # segfault

    # ── Regex pattern match counts ───────────────────────────────
    for pattern in ALL_PATTERNS:
        pid = pattern["id"]
        match_count = sum(1 for p in pattern["patterns"] if p.search(text))
        features[f"regex_{pid}"] = match_count

    return features


def get_feature_names() -> list:
    """Return ordered list of feature names for DataFrame construction."""
    base = [
        "exit_code", "memory_requested_gb", "memory_available_gb", "memory_ratio",
        "n_processes", "n_completed", "n_failed", "completion_ratio",
        "n_lines", "n_error_lines", "n_warning_lines", "error_density",
        "has_stack_trace", "has_oom", "has_permission", "has_disk",
        "has_container", "has_index", "has_schema_error",
        "has_pipeline_failed", "has_conda_error",
        "exit_is_137", "exit_is_1", "exit_is_127", "exit_is_126", "exit_is_139",
    ]
    regex_features = [f"regex_{p['id']}" for p in ALL_PATTERNS]
    return base + regex_features
