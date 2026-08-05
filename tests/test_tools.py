import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flakescope.tools import LogNavigator, dispatch

LOG = (
    "2026-01-01T00:00:00Z ##[group]Run tests\n"
    "2026-01-01T00:00:01Z ok 1\n"
    "2026-01-01T00:00:02Z • [FAIL] something broke\n"
    "2026-01-01T00:00:03Z ##[group]Cleanup\n"
    "2026-01-01T00:00:04Z Post-job cleanup started\n"
    "2026-01-01T00:00:05Z chmod: Permission denied\n"
)


def test_search_finds_failure_strips_timestamp():
    nav = LogNavigator(LOG)
    out = nav.search_log("FAIL")
    assert "[FAIL] something broke" in out and "2026-01-01" not in out


def test_cleanup_is_truncated():
    nav = LogNavigator(LOG)
    assert nav.search_log("Permission denied") == "(no matches)"


def test_list_steps_lists_groups():
    out = LogNavigator(LOG).list_steps()
    assert "Run tests" in out


def test_read_section_is_bounded():
    nav = LogNavigator("\n".join(f"2026-01-01T00:00:00Z line{i}" for i in range(500)))
    out = nav.read_section(0, 999)
    assert out.count("\n") < 121  # capped at 120 lines


def test_dispatch_routes():
    nav = LogNavigator(LOG)
    assert "[FAIL]" in dispatch(nav, "search_log", {"pattern": "FAIL"})
    assert "unknown tool" in dispatch(nav, "nope", {})


def test_bad_regex_is_handled():
    assert "bad regex" in LogNavigator(LOG).search_log("[unclosed")
