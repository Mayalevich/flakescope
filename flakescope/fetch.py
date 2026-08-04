"""Ingest failed CI runs and extract the failure excerpt (GitHub Actions API).

Uses the `gh` CLI for API access (reuses the user's auth, no token handling).
For each failed workflow run we pull the failed jobs, download the job log, and
extract a compact *failure excerpt* — the lines that actually explain the
failure — instead of feeding a multi-MB log to a model. This keeps context
small (a core concern of the project) and makes categorization reproducible:
excerpts are cached to disk keyed by run/job id.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

CACHE = Path(__file__).resolve().parent.parent / "samples"

# GitHub Actions log lines are prefixed with an ISO-8601 timestamp + space.
_TS = re.compile(r"^\S+Z\s")
# Anchors that mark the real failure (vs. post-job cleanup noise).
_ANCHORS = re.compile(
    r"##\[error\]|\[FAILED\]|Summarizing \d+ Failure|"
    r"^\s*FAIL\b|panic:|--- FAIL|Test Suite Failed",
    re.MULTILINE,
)


@dataclass
class FailureCase:
    run_id: int
    job_id: int
    workflow: str
    job_name: str
    head_sha: str
    run_attempt: int          # >1 means it was re-run — a flake signal
    created_at: str
    excerpt: str              # the extracted, timestamp-stripped failure text


def _gh(path: str) -> object:
    out = subprocess.run(
        ["gh", "api", path], capture_output=True, text=True, check=True
    ).stdout
    return json.loads(out)


def _gh_text(path: str) -> str:
    return subprocess.run(
        ["gh", "api", path], capture_output=True, text=True, check=True
    ).stdout


def _strip_ts(text: str) -> str:
    return "\n".join(_TS.sub("", ln) for ln in text.splitlines())


# Everything from here on is runner teardown, not the failure. Its benign
# "Permission denied" / "safe.directory" lines otherwise poison categorization.
_CLEANUP = re.compile(r"Post[- ]job cleanup|Cleaning up orphan processes", re.I)


def extract_failure_excerpt(log: str, window: int = 40, max_lines: int = 250) -> str:
    """Return only the lines around real failure anchors (timestamp-stripped).

    Post-job cleanup noise is dropped first, then windows around real failure
    anchors are merged and capped so a huge log never blows up the context.
    """
    lines = log.splitlines()
    for i, ln in enumerate(lines):  # truncate at the first cleanup marker
        if _CLEANUP.search(ln):
            lines = lines[:i]
            break
    keep: set[int] = set()
    for i, ln in enumerate(lines):
        if _ANCHORS.search(ln):
            keep.update(range(max(0, i - window), min(len(lines), i + window + 1)))
    if not keep:
        # No anchor found: fall back to the tail (last window*2 lines).
        keep = set(range(max(0, len(lines) - window * 2), len(lines)))
    picked = [lines[i] for i in sorted(keep)]
    if len(picked) > max_lines:  # keep the last max_lines (closest to the failure)
        picked = picked[-max_lines:]
    return _strip_ts("\n".join(picked)).strip()


def fetch_failed(repo: str, limit: int = 5) -> list[FailureCase]:
    """Fetch the most recent failed workflow runs and their failed-job excerpts."""
    runs = _gh(f"repos/{repo}/actions/runs?status=failure&per_page={limit}")
    cases: list[FailureCase] = []
    for run in runs["workflow_runs"][:limit]:
        jobs = _gh(f"repos/{repo}/actions/runs/{run['id']}/jobs?per_page=100")
        for job in jobs["jobs"]:
            if job.get("conclusion") != "failure":
                continue
            try:
                raw = _gh_text(f"repos/{repo}/actions/jobs/{job['id']}/logs")
            except subprocess.CalledProcessError:
                continue
            cases.append(
                FailureCase(
                    run_id=run["id"],
                    job_id=job["id"],
                    workflow=run["name"],
                    job_name=job["name"],
                    head_sha=run["head_sha"][:7],
                    run_attempt=run.get("run_attempt", 1),
                    created_at=run["created_at"],
                    excerpt=extract_failure_excerpt(raw),
                )
            )
            break  # one representative failed job per run for the PoC
    return cases


def cache_cases(cases: list[FailureCase]) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    out = CACHE / "failures.json"
    out.write_text(json.dumps([asdict(c) for c in cases], indent=2), encoding="utf-8")
    return out


def load_cases() -> list[FailureCase]:
    data = json.loads((CACHE / "failures.json").read_text(encoding="utf-8"))
    return [FailureCase(**d) for d in data]
