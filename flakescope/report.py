"""Turn categorized failures into a report the dev workflow can consume.

Emits a Markdown flake report (a table plus per-case detail) and a sample
PR-comment block — the two integration surfaces the project asks for.

Flake status combines two independent signals:
  * re-run history (`rerun_passed`) — ground truth: the same workflow passed on
    the same commit, so this failure IS a flake;
  * the failure category — a prior when no re-run evidence exists yet.
"""
from __future__ import annotations

from .categorize import REAL_SIGNALS, Verdict
from .fetch import FailureCase


def flake_status(case: FailureCase, v: Verdict) -> tuple[str, bool]:
    """(human label, is_flake) from re-run evidence first, then the category."""
    if case.rerun_passed:
        return "confirmed flake (re-run passed)", True
    if v.category in REAL_SIGNALS:
        return "likely real", False
    if v.category == "unknown":
        return "needs review", False
    return "suspected flake", True


def markdown_report(rows: list[tuple[FailureCase, Verdict]]) -> str:
    statuses = [flake_status(c, v) for c, v in rows]
    flaky = sum(1 for _, isf in statuses if isf)
    out = ["# CI Flake Report", ""]
    out.append(f"Analyzed **{len(rows)}** failed jobs — **{flaky}** flake / "
               f"suspected-flake, **{len(rows) - flaky}** likely real or needs review.")
    out.append("")
    out.append("| Job | Category | Flake status | Conf | Evidence |")
    out.append("|---|---|---|---|---|")
    for (c, v), (label, _isf) in zip(rows, statuses, strict=True):
        ev = v.evidence.replace("|", "\\|")[:80]
        attempt = " ⟳re-run" if c.run_attempt > 1 else ""
        out.append(f"| {c.job_name[:30]}{attempt} | `{v.category}` | "
                   f"{label} | {v.confidence:.2f} | {ev} |")
    out.append("")
    for (c, v), (label, _isf) in zip(rows, statuses, strict=True):
        out.append(f"### {c.job_name}  ({c.workflow} @ {c.head_sha})")
        out.append(f"- **Category:** `{v.category}` — {v.mitigation}")
        out.append(f"- **Flake status:** {label}  (backend: {v.backend})")
        out.append(f"- **Evidence:** `{v.evidence}`")
        out.append(f"- Run: https://github.com/containers/podman/actions/runs/{c.run_id}")
        out.append("")
    return "\n".join(out)


def pr_comment(case: FailureCase, v: Verdict) -> str:
    label, is_flake = flake_status(case, v)
    tag = "🟡" if is_flake else "🔴"
    return (
        f"{tag} **{label}** — category `{v.category}` (confidence {v.confidence:.0%})\n\n"
        f"> {v.evidence}\n\n"
        f"**Suggested next step:** {v.mitigation}\n\n"
        f"<sub>flakescope · job `{case.job_name}` · run {case.run_id}</sub>"
    )
