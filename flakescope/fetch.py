"""Ingest failed CI runs and extract the failure excerpt (GitHub Actions API).

Uses the `gh` CLI for API access (reuses the user's auth, no token handling).
For each failed workflow run we pull the failed jobs, download the job log, and
extract a compact *failure excerpt* — the lines that actually explain the
failure — instead of feeding a multi-MB log to a model. This keeps context
small (a core concern of the project) and makes categorization reproducible:
excerpts are cached to disk keyed by run/job id.

Flakiness is a property of *re-run history*, not of a single failure: we mark a
failure as a confirmed flake when the same workflow succeeded on the same commit
(head SHA) in another run. The failure *category* is only a prior.
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
# Everything from here on is runner teardown, not the failure. Its benign
# "Permission denied" / "safe.directory" lines otherwise poison categorization.
_CLEANUP = re.compile(r"Post[- ]job cleanup|Cleaning up orphan processes", re.IGNORECASE)
# Artifact/journal upload steps run after the tests and only add noise.
_NOISE = re.compile(r"Artifact .*finalized|No files were found|upload-artifact|"
                    r"successfully finalized|Uploading artifact", re.IGNORECASE)
# Most-informative anchor first: ginkgo's consolidated summary beats a lone marker.
_PRIMARY = [re.compile(p) for p in (
    r"Summarizing \d+ Failure", r"--- FAIL", r"\[FAILED\]", r"panic:", r"##\[error\]")]
# Aggregation/summary jobs that only mirror other jobs' status — not real failures.
_META_JOBS = re.compile(r"^(Total Success|Total|All (Tests|Jobs))\b", re.IGNORECASE)


@dataclass
class FailureCase:
    run_id: int
    job_id: int
    workflow: str
    job_name: str
    head_sha: str
    run_attempt: int          # >1 means this run itself was re-run
    rerun_passed: bool        # same workflow+SHA succeeded elsewhere => confirmed flake
    created_at: str
    excerpt: str              # extracted, timestamp-stripped failure text


def is_real_job(name: str) -> bool:
    """False for aggregation/summary jobs that only mirror other jobs' status."""
    return not _META_JOBS.match(name)


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


def extract_failure_excerpt(log: str, before: int = 160, after: int = 20) -> str:
    """Center the excerpt on the real failure, not the end of a huge log.

    A Podman CI job log can be 100k+ lines with the actual failure in the middle
    and artifact-upload noise at the end. We (1) drop post-job cleanup, (2) drop
    artifact-upload noise lines, then (3) center a window on the most informative
    failure anchor — ginkgo's `Summarizing N Failures` block if present, else the
    LAST real failure marker. Naively keeping the tail would miss the failure.
    """
    lines = log.splitlines()
    for i, ln in enumerate(lines):  # truncate at the first cleanup marker
        if _CLEANUP.search(ln):
            lines = lines[:i]
            break
    lines = [ln for ln in lines if not _NOISE.search(ln)]

    center = None
    for pat in _PRIMARY:  # pick the last match of the most informative anchor kind
        idxs = [i for i, ln in enumerate(lines) if pat.search(ln)]
        if idxs:
            center = idxs[-1]
            break
    if center is None:  # no failure marker in stdout at all -> tail fallback
        window = lines[-(before + after):]
    else:
        window = lines[max(0, center - before): center + after + 1]
    return _strip_ts("\n".join(window)).strip()


def _success_keys(repo: str, per_page: int = 100) -> set[tuple[str, str]]:
    """(workflow_name, head_sha) pairs that have a SUCCESSFUL recent run."""
    runs = _gh(f"repos/{repo}/actions/runs?status=success&per_page={per_page}")
    return {(r["name"], r["head_sha"]) for r in runs["workflow_runs"]}


def fetch_failed(repo: str, limit: int = 5, max_jobs: int = 12) -> list[FailureCase]:
    """Fetch recent failed runs, all their failed jobs, and flake confirmation."""
    failed = _gh(f"repos/{repo}/actions/runs?status=failure&per_page={limit}")
    success = _success_keys(repo)
    cases: list[FailureCase] = []
    for run in failed["workflow_runs"][:limit]:
        jobs = _gh(f"repos/{repo}/actions/runs/{run['id']}/jobs?per_page=100")
        for job in jobs["jobs"]:
            if job.get("conclusion") != "failure" or not is_real_job(job["name"]):
                continue
            try:
                raw = _gh_text(f"repos/{repo}/actions/jobs/{job['id']}/logs")
            except subprocess.CalledProcessError:
                continue
            CACHE.mkdir(parents=True, exist_ok=True)
            (CACHE / f"raw_{job['id']}.log").write_text(raw, encoding="utf-8")
            cases.append(FailureCase(
                run_id=run["id"], job_id=job["id"], workflow=run["name"],
                job_name=job["name"], head_sha=run["head_sha"][:7],
                run_attempt=run.get("run_attempt", 1),
                rerun_passed=(run["name"], run["head_sha"]) in success,
                created_at=run["created_at"],
                excerpt=extract_failure_excerpt(raw),
            ))
            if len(cases) >= max_jobs:
                return cases
    return cases


def cache_cases(cases: list[FailureCase]) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    out = CACHE / "failures.json"
    out.write_text(json.dumps([asdict(c) for c in cases], indent=2), encoding="utf-8")
    return out


def load_cases() -> list[FailureCase]:
    data = json.loads((CACHE / "failures.json").read_text(encoding="utf-8"))
    return [FailureCase(**d) for d in data]


def load_raw(job_id: int) -> str:
    """Raw job log cached during fetch (for the agent to navigate itself).

    Prefers the plain `.log` (fresh fetch); falls back to a committed `.log.gz`
    so the agent eval is reproducible from a clone without re-fetching.
    """
    plain = CACHE / f"raw_{job_id}.log"
    if plain.exists():
        return plain.read_text(encoding="utf-8")
    import gzip
    return gzip.decompress((CACHE / f"raw_{job_id}.log.gz").read_bytes()).decode("utf-8")
