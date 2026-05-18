"""
classifier.py - Rule-based failure classifier.
Extend with ML (scikit-learn) later.
"""


def classify_failure(parsed_log: dict) -> dict:
    """Classify pipeline failures from parsed log output."""
    detected = parsed_log.get("detected", [])
    meta = parsed_log.get("meta", {})

    severity_counts = {"critical": 0, "high": 0, "medium": 0}
    for d in detected:
        sev = d.get("severity", "medium")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    if severity_counts["critical"] > 0:
        run_health = "failed"
    elif severity_counts["high"] > 0 or detected:
        run_health = "degraded"
    else:
        run_health = "healthy"

    primary = detected[0] if detected else None

    if not detected:
        triage = "No known error patterns detected in this log."
    elif primary:
        proc = meta.get("failed_process") or "unknown process"
        triage = (
            f"{primary['icon']} {primary['label']} detected in {proc} "
            f"(confidence: {primary['confidence']:.0%}, severity: {primary['severity']})"
        )
    else:
        triage = "Errors detected but could not determine primary failure."

    return {
        "primary_failure": primary,
        "all_failures": detected,
        "triage_summary": triage,
        "severity_counts": severity_counts,
        "run_health": run_health,
    }
