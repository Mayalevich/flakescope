import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flakescope.categorize import categorize_heuristic
from flakescope.fetch import (
    FailureCase,
    extract_failure_excerpt,
    is_real_job,
)
from flakescope.report import flake_status, pr_comment


def _case(**kw) -> FailureCase:
    base = dict(run_id=1, job_id=1, workflow="ci", job_name="job", head_sha="abc1234",
                run_attempt=1, rerun_passed=False, created_at="", excerpt="")
    base.update(kw)
    return FailureCase(**base)


def test_network_is_flake():
    v = categorize_heuristic("dial tcp 1.2.3.4:443: connect: connection refused")
    assert v.category == "network_timeout" and v.is_flake


def test_lint_is_not_flake():
    v = categorize_heuristic("runtime_ctr.go:12:1: File is not properly formatted (gofumpt)")
    assert v.category == "lint_format" and not v.is_flake


def test_real_assertion_beats_weak_timeout():
    # Conservative policy: a genuine assertion + only a *weak* timeout signal must
    # NOT be hidden as a flake (that would auto-retry a real bug).
    excerpt = "• [FAILED] Expected 0 to equal 1\noperation timed out after 5s"
    v = categorize_heuristic(excerpt)
    assert v.category == "real_test_bug" and not v.is_flake


def test_strong_infra_overrides_assertion():
    # A *strong* environment signal (connection refused) alongside an assertion
    # reads as a flake, but with reduced confidence.
    excerpt = "Expected err to be nil\ndial tcp: connect: connection refused"
    v = categorize_heuristic(excerpt)
    assert v.category == "network_timeout" and v.is_flake and v.confidence <= 0.5


def test_extract_drops_cleanup_noise():
    log = (
        "2026-01-01T00:00:00Z • [FAILED] real failure here\n"
        "2026-01-01T00:00:01Z Post-job cleanup started\n"
        "2026-01-01T00:00:02Z chmod: Permission denied\n"
    )
    ex = extract_failure_excerpt(log)
    assert "real failure here" in ex and "Permission denied" not in ex


def test_rerun_pass_confirms_flake_even_if_category_real():
    # Re-run history is ground truth: if it passed on re-run, it's a flake
    # regardless of what the single log looked like.
    c = _case(rerun_passed=True)
    v = categorize_heuristic("• [FAILED] Expected 0 to equal 1")
    label, is_flake = flake_status(c, v)
    assert is_flake and "confirmed flake" in label


def test_meta_job_regex_filters_aggregators():
    assert is_real_job("Total Success") is False
    assert is_real_job("sys local root fedora") is True


def test_pr_comment_has_evidence_and_status():
    c = _case(rerun_passed=True)
    v = categorize_heuristic("dial tcp: connection refused")
    txt = pr_comment(c, v)
    assert "confirmed flake" in txt and "connection refused" in txt
