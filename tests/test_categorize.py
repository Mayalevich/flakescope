import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flakescope.categorize import categorize_heuristic  # noqa: E402
from flakescope.fetch import extract_failure_excerpt  # noqa: E402


def test_network_is_flake():
    v = categorize_heuristic("dial tcp 1.2.3.4:443: connect: connection refused")
    assert v.category == "network_timeout" and v.is_flake


def test_lint_is_not_flake():
    v = categorize_heuristic("runtime_ctr.go:12:1: File is not properly formatted (gofumpt)")
    assert v.category == "lint_format" and not v.is_flake


def test_real_assertion_is_not_flake():
    v = categorize_heuristic("• [FAILED] Expected 0 to equal 1\n--- FAIL: TestFoo")
    assert not v.is_flake


def test_infra_signal_beats_bare_assertion():
    # A network blip alongside a downstream assertion should read as a flake.
    excerpt = "Expected error to be nil\ni/o timeout while pulling image"
    assert categorize_heuristic(excerpt).is_flake


def test_extract_drops_cleanup_noise():
    log = (
        "2026-01-01T00:00:00Z • [FAILED] real failure here\n"
        "2026-01-01T00:00:01Z Post-job cleanup started\n"
        "2026-01-01T00:00:02Z chmod: Permission denied\n"
    )
    ex = extract_failure_excerpt(log)
    assert "real failure here" in ex and "Permission denied" not in ex
