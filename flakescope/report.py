"""Turn categorized failures into a report the dev workflow can consume.

Emits a Markdown flake report (a table plus per-case detail) and a sample
PR-comment block — the two integration surfaces the project asks for.
"""
from __future__ import annotations

from .categorize import Verdict
from .fetch import FailureCase


def markdown_report(rows: list[tuple[FailureCase, Verdict]]) -> str:
    flaky = sum(1 for _, v in rows if v.is_flake)
    out = ["# CI Flake Report", ""]
    out.append(f"Analyzed **{len(rows)}** failed jobs — "
               f"**{flaky}** look like flakes, **{len(rows) - flaky}** look like real failures.")
    out.append("")
    out.append("| Job | Category | Flake? | Conf | Backend | Evidence |")
    out.append("|---|---|---|---|---|---|")
    for c, v in rows:
        ev = v.evidence.replace("|", "\\|")[:80]
        attempt = " ⟳re-run" if c.run_attempt > 1 else ""
        out.append(f"| {c.job_name[:32]}{attempt} | `{v.category}` | "
                   f"{'✅' if v.is_flake else '❌'} | {v.confidence:.2f} | {v.backend} | {ev} |")
    out.append("")
    for c, v in rows:
        out.append(f"### {c.job_name}  ({c.workflow} @ {c.head_sha})")
        out.append(f"- **Category:** `{v.category}` — {'likely flake' if v.is_flake else 'likely real bug'}")
        out.append(f"- **Evidence:** `{v.evidence}`")
        out.append(f"- **Suggested mitigation:** {v.mitigation}")
        out.append(f"- Run: https://github.com/containers/podman/actions/runs/{c.run_id}")
        out.append("")
    return "\n".join(out)


def pr_comment(case: FailureCase, v: Verdict) -> str:
    tag = "🟡 Likely flake" if v.is_flake else "🔴 Likely real failure"
    return (
        f"{tag} — `{v.category}` (confidence {v.confidence:.0%})\n\n"
        f"> {v.evidence}\n\n"
        f"**Suggested next step:** {v.mitigation}\n\n"
        f"<sub>flakescope · job `{case.job_name}` · run {case.run_id}</sub>"
    )
