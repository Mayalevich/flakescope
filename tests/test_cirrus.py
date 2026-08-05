import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flakescope.fetch_cirrus import builds_to_cases  # noqa: E402

# A sample Cirrus GraphQL `ownerRepository` payload. `int fedora` FAILED in build
# b1 but COMPLETED on the same commit in b2 -> it is a confirmed flake.
SAMPLE = {
    "builds": {"edges": [
        {"node": {
            "id": "b1", "status": "FAILED", "changeIdInRepo": "abc123def456",
            "branch": "main", "buildCreatedTimestamp": 1700000000000,
            "tasks": [
                {"id": "t1", "name": "int fedora", "status": "FAILED",
                 "commands": [{"name": "main"}]},
                {"id": "t2", "name": "unit fedora", "status": "COMPLETED",
                 "commands": [{"name": "main"}]},
            ]}},
        {"node": {
            "id": "b2", "status": "COMPLETED", "changeIdInRepo": "abc123def456",
            "branch": "main", "buildCreatedTimestamp": 1700000100000,
            "tasks": [{"id": "t3", "name": "int fedora", "status": "COMPLETED",
                       "commands": [{"name": "main"}]}]}},
    ]}
}


def _fake_log(task_id, commands):
    assert commands == ["main"]
    return f"2026Z running {task_id}\n2026Z [FAIL] Podman run networking [It] two static IPs"


def test_only_failed_tasks_become_cases():
    cases = builds_to_cases(SAMPLE, _fake_log)
    assert len(cases) == 1  # t2/t3 COMPLETED are skipped
    assert cases[0].job_name == "int fedora"


def test_maps_fields_and_reuses_excerpt():
    c = builds_to_cases(SAMPLE, _fake_log)[0]
    assert c.job_id == "t1"
    assert c.head_sha == "abc123d"
    assert c.workflow == "cirrus/main"
    assert "two static IPs" in c.excerpt  # extract_failure_excerpt reused


def test_rerun_passed_confirms_flake_across_builds():
    # int fedora COMPLETED on the same commit in b2 -> the b1 failure is a flake.
    assert builds_to_cases(SAMPLE, _fake_log)[0].rerun_passed is True
