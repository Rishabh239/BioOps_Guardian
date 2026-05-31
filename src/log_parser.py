"""
log_parser.py - Parse Nextflow log files and detect error patterns.
"""
import re
from src.patterns import ERROR_PATTERNS
from src.scrna_patterns import SCRNA_PATTERNS
ALL_PATTERNS = ERROR_PATTERNS + SCRNA_PATTERNS


def parse_nextflow_log(text: str) -> dict:
    """Parse a Nextflow log and return structured diagnostics."""
    detected = []
    processes = []

    # Extract process execution lines
    proc_re = re.compile(
        r"\[([a-f0-9]{2}/[a-f0-9]{6})\]\s+process\s*>\s*(.+?)\s+"
        r"\[(\s*\d+%)\]\s*(\d+)\s+of\s+(\d+)",
        re.I,
    )
    for m in proc_re.finditer(text):
        progress = m.group(3).strip()
        processes.append({
            "hash": m.group(1),
            "name": m.group(2).strip(),
            "progress": progress,
            "completed": int(m.group(4)),
            "total": int(m.group(5)),
            "done": progress == "100%",
        })

    # Extract run metadata
    def _first(pattern, flags=0):
        m = re.search(pattern, text, flags)
        return m.group(1).strip() if m else None

    meta = {
        "nf_version": _first(r"N E X T F L O W\s+~\s+version\s+([\d.]+)"),
        "pipeline": _first(r"Launching\s+`([^`]+)`"),
        "revision": _first(r"revision:\s*(\S+)"),
        "failed_process": _first(r"Error executing process\s*>\s*'([^']+)'", re.I),
        "work_dir": _first(r"Work dir:\s*(\S+)", re.I),
        "command": _first(r"Command executed:\s*\n\s*(.+)", re.I),
        "exit_status": _first(r"Command exit status:\s*(.+)", re.I),
    }

    # Match error patterns
    lines = text.split("\n")
    for pattern in ALL_PATTERNS:
        matched_regexes = [p for p in pattern["patterns"] if p.search(text)]
        if not matched_regexes:
            continue

        matched_lines = []
        for idx, line in enumerate(lines):
            if any(p.search(line) for p in matched_regexes):
                matched_lines.append({"line_num": idx + 1, "text": line.strip()})

        confidence = min(0.5 + len(matched_regexes) * 0.2, 0.99)

        detected.append({
            "id": pattern["id"],
            "label": pattern["label"],
            "severity": pattern["severity"],
            "icon": pattern["icon"],
            "cause": pattern["cause"],
            "fix": pattern["fix"],
            "command": pattern["command"],
            "match_count": len(matched_regexes),
            "confidence": confidence,
            "matched_lines": matched_lines,
        })

    detected.sort(key=lambda d: d["confidence"], reverse=True)

    return {
        "detected": detected,
        "processes": processes,
        "meta": meta,
        "total_processes": len(processes),
        "completed_processes": sum(1 for p in processes if p["done"]),
        "failed_processes": sum(1 for p in processes if not p["done"]),
    }
