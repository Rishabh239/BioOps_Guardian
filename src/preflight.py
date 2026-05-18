"""
preflight.py - Pre-flight validation for Nextflow pipeline runs.

Checks everything BEFORE you launch a run:
  1. Sample sheet validation (columns, IDs, paths, strandedness)
  2. Input file existence (FASTQs listed in sample sheet)
  3. Reference file existence (genome, index, GTF)
  4. nextflow.config parsing (memory, CPUs, container settings)
  5. Disk space estimation
  6. Container/Conda availability
  7. Memory sufficiency (known genome sizes vs config)

Usage:
    from src.preflight import run_preflight
    results = run_preflight(
        samplesheet_path="/path/to/samplesheet.csv",
        config_path="/path/to/nextflow.config",
        work_dir="/path/to/work",
    )
"""

import os
import re
import shutil
import subprocess
from pathlib import Path
from src.sample_validator import validate_sample_sheet


# ── Known genome sizes for memory estimation ─────────────────────
GENOME_MEMORY_REQUIREMENTS = {
    # genome_name: {"star_gb": min GB for STAR, "bwa_gb": min GB for BWA}
    "GRCh38": {"star_gb": 32, "bwa_gb": 8, "hisat2_gb": 8, "size_gb": 3.1},
    "GRCh37": {"star_gb": 32, "bwa_gb": 8, "hisat2_gb": 8, "size_gb": 3.0},
    "hg38": {"star_gb": 32, "bwa_gb": 8, "hisat2_gb": 8, "size_gb": 3.1},
    "hg19": {"star_gb": 32, "bwa_gb": 8, "hisat2_gb": 8, "size_gb": 3.0},
    "GRCm39": {"star_gb": 32, "bwa_gb": 6, "hisat2_gb": 6, "size_gb": 2.7},
    "GRCm38": {"star_gb": 32, "bwa_gb": 6, "hisat2_gb": 6, "size_gb": 2.7},
    "mm10": {"star_gb": 32, "bwa_gb": 6, "hisat2_gb": 6, "size_gb": 2.7},
    "mm39": {"star_gb": 32, "bwa_gb": 6, "hisat2_gb": 6, "size_gb": 2.7},
    "T2T": {"star_gb": 36, "bwa_gb": 10, "hisat2_gb": 10, "size_gb": 3.1},
    "TAIR10": {"star_gb": 4, "bwa_gb": 1, "hisat2_gb": 1, "size_gb": 0.12},
    "WBcel235": {"star_gb": 4, "bwa_gb": 1, "hisat2_gb": 1, "size_gb": 0.1},
    "R64-1-1": {"star_gb": 4, "bwa_gb": 1, "hisat2_gb": 1, "size_gb": 0.012},
    "dm6": {"star_gb": 8, "bwa_gb": 2, "hisat2_gb": 2, "size_gb": 0.14},
    "danRer11": {"star_gb": 16, "bwa_gb": 4, "hisat2_gb": 4, "size_gb": 1.4},
}

# Rough estimate: ~5GB work dir space per sample for RNA-seq
DISK_PER_SAMPLE_GB = 5


def _parse_config(config_text):
    """Extract key settings from a nextflow.config file."""
    settings = {
        "max_memory": None,
        "max_cpus": None,
        "max_time": None,
        "container_engine": None,
        "genome": None,
        "fasta": None,
        "gtf": None,
        "star_index": None,
        "bwa_index": None,
        "hisat2_index": None,
        "outdir": None,
        "executor": None,
        "profile": None,
    }

    # Memory: various formats
    mem_match = re.search(r"max_memory\s*=\s*['\"]?([\d.]+)\s*\.?\s*GB['\"]?", config_text, re.I)
    if mem_match:
        settings["max_memory"] = float(mem_match.group(1))

    # CPUs
    cpu_match = re.search(r"max_cpus\s*=\s*['\"]?(\d+)['\"]?", config_text, re.I)
    if cpu_match:
        settings["max_cpus"] = int(cpu_match.group(1))

    # Time
    time_match = re.search(r"max_time\s*=\s*['\"]?([\d.]+)\s*\.?\s*h['\"]?", config_text, re.I)
    if time_match:
        settings["max_time"] = float(time_match.group(1))

    # Container engine
    for engine in ["docker", "singularity", "podman", "conda", "mamba"]:
        if re.search(rf"{engine}\s*\{{\s*enabled\s*=\s*true", config_text, re.I):
            settings["container_engine"] = engine
            break
        if re.search(rf"profile.*{engine}", config_text, re.I):
            settings["container_engine"] = engine

    # Genome
    genome_match = re.search(r"genome\s*=\s*['\"]?([A-Za-z0-9_.\-]+)['\"]?", config_text, re.M)
    if genome_match:
        settings["genome"] = genome_match.group(1).strip("'\"")

    # File paths
    for key in ["fasta", "gtf", "star_index", "bwa_index", "hisat2_index", "outdir"]:
        match = re.search(rf"{key}\s*=\s*['\"]?([^\s'\"]+)['\"]?", config_text, re.I)
        if match:
            settings[key] = match.group(1)

    # Executor
    exec_match = re.search(r"executor\s*=\s*['\"]?(\w+)['\"]?", config_text, re.I)
    if exec_match:
        settings["executor"] = exec_match.group(1)

    return settings


def _check_file_exists(path_str):
    """Check if a file path exists. Handles ~ expansion."""
    if not path_str:
        return None
    path = Path(os.path.expanduser(path_str))
    return path.exists()


def _check_command_available(cmd):
    """Check if a command is available on PATH."""
    try:
        result = subprocess.run(
            ["which", cmd] if os.name != "nt" else ["where", cmd],
            capture_output=True, timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _get_disk_free_gb(path):
    """Get free disk space in GB for the given path."""
    try:
        usage = shutil.disk_usage(os.path.expanduser(path))
        return round(usage.free / (1024**3), 1)
    except (OSError, FileNotFoundError):
        return None


def _estimate_disk_needed(n_samples, genome_size_gb=3.0):
    """Estimate disk space needed for a run."""
    return round(n_samples * DISK_PER_SAMPLE_GB + genome_size_gb * 2, 1)


def check_samplesheet(samplesheet_text=None, samplesheet_path=None):
    """Validate sample sheet and check if FASTQ files exist."""
    checks = []

    if samplesheet_path and not samplesheet_text:
        path = Path(os.path.expanduser(samplesheet_path))
        if not path.exists():
            checks.append({
                "check": "Sample sheet file",
                "status": "fail",
                "severity": "critical",
                "message": f"Sample sheet not found: {samplesheet_path}",
            })
            return checks, None
        samplesheet_text = path.read_text()

    if not samplesheet_text:
        checks.append({
            "check": "Sample sheet",
            "status": "skip",
            "severity": "info",
            "message": "No sample sheet provided",
        })
        return checks, None

    # Run the existing validator
    result = validate_sample_sheet(samplesheet_text)

    for issue in result.get("issues", []):
        checks.append({
            "check": "Sample sheet validation",
            "status": "fail" if issue["type"] == "critical" else "warn",
            "severity": issue["type"],
            "message": issue["message"],
        })

    if not result.get("issues"):
        checks.append({
            "check": "Sample sheet validation",
            "status": "pass",
            "severity": "info",
            "message": "Sample sheet structure is valid",
        })

    # Check if FASTQ files actually exist on disk
    summary = result.get("summary")
    if summary:
        lines = samplesheet_text.strip().split("\n")
        header = [h.strip().lower() for h in lines[0].split(",")]
        fq1_idx = header.index("fastq_1") if "fastq_1" in header else -1
        fq2_idx = header.index("fastq_2") if "fastq_2" in header else -1

        missing_files = []
        checked_files = 0
        for row in lines[1:]:
            if not row.strip():
                continue
            cols = [c.strip() for c in row.split(",")]
            for idx in [fq1_idx, fq2_idx]:
                if idx >= 0 and idx < len(cols) and cols[idx]:
                    fpath = cols[idx]
                    # Only check local paths (not s3://, gs://, etc.)
                    if not fpath.startswith("s3://") and not fpath.startswith("gs://") and not fpath.startswith("az://"):
                        checked_files += 1
                        if not _check_file_exists(fpath):
                            missing_files.append(fpath)

        if missing_files:
            checks.append({
                "check": "FASTQ file existence",
                "status": "fail",
                "severity": "critical",
                "message": f"{len(missing_files)} of {checked_files} FASTQ files not found on disk",
                "details": missing_files[:10],  # show first 10
            })
        elif checked_files > 0:
            checks.append({
                "check": "FASTQ file existence",
                "status": "pass",
                "severity": "info",
                "message": f"All {checked_files} FASTQ files found on disk",
            })

    return checks, summary


def check_config(config_text=None, config_path=None):
    """Parse and validate nextflow.config."""
    checks = []

    if config_path and not config_text:
        path = Path(os.path.expanduser(config_path))
        if not path.exists():
            checks.append({
                "check": "Config file",
                "status": "fail",
                "severity": "critical",
                "message": f"Config file not found: {config_path}",
            })
            return checks, {}
        config_text = path.read_text()

    if not config_text:
        checks.append({
            "check": "Config file",
            "status": "skip",
            "severity": "info",
            "message": "No config provided — using defaults",
        })
        return checks, {}

    # Check for syntax issues
    brace_count = config_text.count("{") - config_text.count("}")
    if brace_count != 0:
        checks.append({
            "check": "Config syntax",
            "status": "fail",
            "severity": "critical",
            "message": f"Mismatched braces in config: {abs(brace_count)} {'extra opening' if brace_count > 0 else 'extra closing'} brace(s)",
        })

    settings = _parse_config(config_text)

    # Check memory
    if settings["max_memory"]:
        if settings["max_memory"] < 4:
            checks.append({
                "check": "Memory allocation",
                "status": "warn",
                "severity": "warning",
                "message": f"max_memory is very low ({settings['max_memory']} GB). Most NGS tools need at least 8 GB.",
            })
        else:
            checks.append({
                "check": "Memory allocation",
                "status": "pass",
                "severity": "info",
                "message": f"max_memory = {settings['max_memory']} GB",
            })
    else:
        checks.append({
            "check": "Memory allocation",
            "status": "warn",
            "severity": "warning",
            "message": "max_memory not found in config — pipeline will use defaults",
        })

    # Check CPUs
    if settings["max_cpus"]:
        checks.append({
            "check": "CPU allocation",
            "status": "pass",
            "severity": "info",
            "message": f"max_cpus = {settings['max_cpus']}",
        })

    # Check container engine
    if settings["container_engine"]:
        checks.append({
            "check": "Container/Environment engine",
            "status": "pass",
            "severity": "info",
            "message": f"Using {settings['container_engine']}",
        })
    else:
        checks.append({
            "check": "Container/Environment engine",
            "status": "warn",
            "severity": "warning",
            "message": "No container engine detected in config (docker/singularity/conda). Pipeline may fail if tools aren't installed locally.",
        })

    return checks, settings


def check_references(settings, config_text=""):
    """Check if reference files exist and are sufficient."""
    checks = []

    # Check genome FASTA
    fasta = settings.get("fasta")
    if fasta:
        if _check_file_exists(fasta):
            # Check file size
            fasta_size = Path(os.path.expanduser(fasta)).stat().st_size / (1024**3)
            checks.append({
                "check": "Genome FASTA",
                "status": "pass",
                "severity": "info",
                "message": f"Found: {fasta} ({fasta_size:.2f} GB)",
            })
        else:
            checks.append({
                "check": "Genome FASTA",
                "status": "fail",
                "severity": "critical",
                "message": f"Genome FASTA not found: {fasta}",
            })

    # Check GTF
    gtf = settings.get("gtf")
    if gtf:
        if _check_file_exists(gtf):
            checks.append({
                "check": "Gene annotation (GTF)",
                "status": "pass",
                "severity": "info",
                "message": f"Found: {gtf}",
            })
        else:
            checks.append({
                "check": "Gene annotation (GTF)",
                "status": "fail",
                "severity": "critical",
                "message": f"GTF file not found: {gtf}",
            })

    # Check indices
    for idx_name, idx_key in [("STAR index", "star_index"), ("BWA index", "bwa_index"), ("HISAT2 index", "hisat2_index")]:
        idx_path = settings.get(idx_key)
        if idx_path:
            if _check_file_exists(idx_path):
                checks.append({
                    "check": idx_name,
                    "status": "pass",
                    "severity": "info",
                    "message": f"Found: {idx_path}",
                })
            else:
                checks.append({
                    "check": idx_name,
                    "status": "fail",
                    "severity": "critical",
                    "message": f"{idx_name} not found: {idx_path}. It will need to be built (adds time to run).",
                })

    return checks


def check_memory_sufficiency(settings, n_samples=0):
    """Check if allocated memory is enough for the genome."""
    checks = []
    genome = settings.get("genome") or ""
    max_mem = settings.get("max_memory")

    if not max_mem:
        return checks

    # Try to match genome name
    genome_info = None
    for gname, info in GENOME_MEMORY_REQUIREMENTS.items():
        if gname.lower() in genome.lower():
            genome_info = info
            break

    if genome_info:
        # Check STAR memory
        if max_mem < genome_info["star_gb"]:
            checks.append({
                "check": "Memory for STAR alignment",
                "status": "fail",
                "severity": "critical",
                "message": (
                    f"STAR index for {genome} needs ~{genome_info['star_gb']} GB but max_memory is {max_mem} GB. "
                    f"Increase to at least {genome_info['star_gb']} GB or STAR will crash with OOM."
                ),
            })
        else:
            checks.append({
                "check": "Memory for STAR alignment",
                "status": "pass",
                "severity": "info",
                "message": f"max_memory ({max_mem} GB) is sufficient for STAR on {genome} (needs ~{genome_info['star_gb']} GB)",
            })

    return checks


def check_disk_space(work_dir, n_samples, genome_name=""):
    """Check if there's enough disk space for the run."""
    checks = []
    genome_name = genome_name or ""

    if not work_dir:
        work_dir = "."

    free_gb = _get_disk_free_gb(work_dir)
    if free_gb is None:
        checks.append({
            "check": "Disk space",
            "status": "skip",
            "severity": "info",
            "message": f"Could not check disk space at: {work_dir}",
        })
        return checks

    # Estimate needed space
    genome_size = 3.0  # default
    for gname, info in GENOME_MEMORY_REQUIREMENTS.items():
        if gname.lower() in genome_name.lower():
            genome_size = info["size_gb"]
            break

    needed_gb = _estimate_disk_needed(n_samples, genome_size)

    if free_gb < needed_gb:
        checks.append({
            "check": "Disk space",
            "status": "fail",
            "severity": "critical",
            "message": (
                f"Estimated {needed_gb} GB needed for {n_samples} samples, "
                f"but only {free_gb} GB free at {work_dir}"
            ),
        })
    elif free_gb < needed_gb * 1.5:
        checks.append({
            "check": "Disk space",
            "status": "warn",
            "severity": "warning",
            "message": (
                f"Tight on space: {free_gb} GB free, estimated {needed_gb} GB needed. "
                f"Consider cleaning old work directories first."
            ),
        })
    else:
        checks.append({
            "check": "Disk space",
            "status": "pass",
            "severity": "info",
            "message": f"{free_gb} GB free, estimated {needed_gb} GB needed — sufficient",
        })

    return checks


def check_tools(settings):
    """Check if required tools/engines are available."""
    checks = []

    # Check Nextflow itself
    if _check_command_available("nextflow"):
        checks.append({
            "check": "Nextflow installed",
            "status": "pass",
            "severity": "info",
            "message": "Nextflow is available on PATH",
        })
    else:
        checks.append({
            "check": "Nextflow installed",
            "status": "fail",
            "severity": "critical",
            "message": "Nextflow not found on PATH. Install from https://nextflow.io",
        })

    # Check container engine
    engine = settings.get("container_engine")
    if engine:
        if _check_command_available(engine):
            checks.append({
                "check": f"{engine.title()} available",
                "status": "pass",
                "severity": "info",
                "message": f"{engine} is available on PATH",
            })
        else:
            checks.append({
                "check": f"{engine.title()} available",
                "status": "fail",
                "severity": "critical",
                "message": f"{engine} is configured but not found on PATH",
            })

    # Check Java
    if _check_command_available("java"):
        checks.append({
            "check": "Java installed",
            "status": "pass",
            "severity": "info",
            "message": "Java is available (required by Nextflow)",
        })
    else:
        checks.append({
            "check": "Java installed",
            "status": "fail",
            "severity": "critical",
            "message": "Java not found — required by Nextflow",
        })

    return checks


def run_preflight(
    samplesheet_text=None,
    samplesheet_path=None,
    config_text=None,
    config_path=None,
    work_dir=None,
):
    """Run all pre-flight checks and return a structured report.

    Returns:
        dict with: checks (list), summary (pass/warn/fail counts), verdict
    """
    all_checks = []

    # 1. Sample sheet
    sheet_checks, sheet_summary = check_samplesheet(
        samplesheet_text=samplesheet_text,
        samplesheet_path=samplesheet_path,
    )
    all_checks.extend(sheet_checks)

    n_samples = sheet_summary["total_samples"] if sheet_summary else 0

    # 2. Config
    config_checks, settings = check_config(
        config_text=config_text,
        config_path=config_path,
    )
    all_checks.extend(config_checks)

    # 3. References
    if settings:
        ref_checks = check_references(settings, config_text or "")
        all_checks.extend(ref_checks)

    # 4. Memory sufficiency
    if settings:
        mem_checks = check_memory_sufficiency(settings, n_samples)
        all_checks.extend(mem_checks)

    # 5. Disk space
    disk_checks = check_disk_space(
        work_dir or settings.get("outdir", ".") or ".",
        n_samples,
        settings.get("genome") or "",
    )
    all_checks.extend(disk_checks)

    # 6. Tools
    tool_checks = check_tools(settings)
    all_checks.extend(tool_checks)

    # Summary
    n_pass = sum(1 for c in all_checks if c["status"] == "pass")
    n_warn = sum(1 for c in all_checks if c["status"] == "warn")
    n_fail = sum(1 for c in all_checks if c["status"] == "fail")
    n_skip = sum(1 for c in all_checks if c["status"] == "skip")

    if n_fail > 0:
        verdict = "fail"
        verdict_msg = f"🔴 NOT READY — {n_fail} critical issue(s) found. Fix these before launching."
    elif n_warn > 0:
        verdict = "warn"
        verdict_msg = f"🟡 PROCEED WITH CAUTION — {n_warn} warning(s). Review before launching."
    else:
        verdict = "pass"
        verdict_msg = f"🟢 READY TO LAUNCH — all {n_pass} checks passed."

    return {
        "checks": all_checks,
        "summary": {
            "pass": n_pass,
            "warn": n_warn,
            "fail": n_fail,
            "skip": n_skip,
            "total": len(all_checks),
        },
        "verdict": verdict,
        "verdict_message": verdict_msg,
        "config_settings": settings,
        "sheet_summary": sheet_summary,
    }
