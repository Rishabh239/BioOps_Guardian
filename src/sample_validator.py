"""
sample_validator.py - Validate nf-core style sample sheets (CSV).
"""
import re
from src.patterns import REQUIRED_COLUMNS, VALID_STRANDEDNESS


def validate_sample_sheet(text: str) -> dict:
    """Validate a CSV sample sheet and return issues + summary."""
    issues = []
    lines = text.strip().split("\n")

    if len(lines) < 2:
        issues.append({"type": "critical", "message": "Sample sheet is empty or has no data rows."})
        return {"issues": issues, "summary": None}

    header = [h.strip().lower() for h in lines[0].split(",")]
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        issues.append({"type": "critical", "message": f"Missing required columns: {', '.join(missing)}"})

    def _col(name):
        return header.index(name) if name in header else -1

    sample_idx = _col("sample")
    fq1_idx = _col("fastq_1")
    fq2_idx = _col("fastq_2")
    strand_idx = _col("strandedness")

    data_rows = [l for l in lines[1:] if l.strip()]
    sample_ids = []
    single_end = 0
    paired_end = 0

    for i, row in enumerate(data_rows):
        cols = [c.strip() for c in row.split(",")]
        row_num = i + 2

        if sample_idx >= 0:
            sid = cols[sample_idx] if sample_idx < len(cols) else ""
            if not sid:
                issues.append({"type": "critical", "message": f"Row {row_num}: Empty sample ID."})
            else:
                sample_ids.append(sid)

        fq1 = ""
        if fq1_idx >= 0:
            fq1 = cols[fq1_idx] if fq1_idx < len(cols) else ""
            if not fq1:
                issues.append({"type": "critical", "message": f"Row {row_num}: Missing fastq_1 path."})
            elif not (fq1.endswith(".fastq.gz") or fq1.endswith(".fq.gz")):
                issues.append({"type": "warning", "message": f"Row {row_num}: fastq_1 doesn't end with .fastq.gz or .fq.gz."})

        fq2 = ""
        if fq2_idx >= 0:
            fq2 = cols[fq2_idx] if fq2_idx < len(cols) else ""
            if fq1 and not fq2:
                issues.append({"type": "info", "message": f"Row {row_num}: No fastq_2 -- will be treated as single-end."})
                single_end += 1
            elif fq2:
                paired_end += 1
                if not (fq2.endswith(".fastq.gz") or fq2.endswith(".fq.gz")):
                    issues.append({"type": "warning", "message": f"Row {row_num}: fastq_2 doesn't end with .fastq.gz or .fq.gz."})

        if fq1 and fq2:
            base1 = re.sub(r"_R1|_1", "", fq1)
            base2 = re.sub(r"_R2|_2", "", fq2)
            if base1 != base2:
                issues.append({"type": "warning", "message": f"Row {row_num}: Paired-end filenames don't follow R1/R2 naming convention."})

        if strand_idx >= 0:
            strand = cols[strand_idx].lower() if strand_idx < len(cols) else ""
            if strand and strand not in VALID_STRANDEDNESS:
                issues.append({
                    "type": "critical",
                    "message": f'Row {row_num}: Invalid strandedness "{cols[strand_idx]}". Must be one of: {", ".join(VALID_STRANDEDNESS)}',
                })

    seen = {}
    for sid in sample_ids:
        seen[sid] = seen.get(sid, 0) + 1
    for sid, count in seen.items():
        if count > 1:
            issues.append({
                "type": "warning",
                "message": f'Duplicate sample ID "{sid}" appears {count} times. Ensure this is intentional (e.g., multi-lane sequencing).',
            })

    return {
        "issues": issues,
        "summary": {
            "total_samples": len(data_rows),
            "unique_samples": len(set(sample_ids)),
            "columns": header,
            "single_end": single_end,
            "paired_end": paired_end,
        },
    }
