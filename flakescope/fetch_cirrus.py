"""Cirrus CI ingestion — Podman's *primary* CI (the GitHub Actions path is a subset).

Podman runs most of its test matrix on Cirrus CI, and its existing flake tooling
(cirrus-flake-xref, containers/automation) lives there. This adds a Cirrus source
that produces the same `FailureCase` shape, so the identical excerpt / categorize
/ agent / report pipeline works on Cirrus too.

> **STATUS: written to the Cirrus API, NOT run in this environment.** The sandbox
> this was developed in blocks `api.cirrus-ci.com` (connection reset), so the two
> network functions below are unvalidated here — they follow the documented Cirrus
> GraphQL API and the `/v1/task/{id}/logs/{command}.log` REST endpoint, and need a
> networked machine to confirm. The pure transform (`builds_to_cases`) that turns
> a GraphQL response into `FailureCase`s IS unit-tested (`tests/test_cirrus.py`).

Cirrus GraphQL (POST https://api.cirrus-ci.com/graphql):
    ownerRepository(platform,owner,name){ builds(last){ edges{ node{
        id status changeIdInRepo branch buildCreatedTimestamp
        tasks{ id name status commands{ name } } } } } }
Task command log (GET): https://api.cirrus-ci.com/v1/task/{taskId}/logs/{command}.log
"""
from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable

from .fetch import FailureCase, extract_failure_excerpt

GRAPHQL = "https://api.cirrus-ci.com/graphql"
LOG_URL = "https://api.cirrus-ci.com/v1/task/{task}/logs/{command}.log"

_BUILDS_QUERY = """
query($owner:String!,$name:String!,$last:Int!){
  ownerRepository(platform:"github", owner:$owner, name:$name){
    builds(last:$last){ edges{ node{
      id status changeIdInRepo branch buildCreatedTimestamp
      tasks{ id name status commands{ name } } } } } } }
"""


# ---- network (unvalidated in this sandbox) ---------------------------------
def cirrus_graphql(query: str, variables: dict) -> dict:
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(GRAPHQL, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:  # pragma: no cover - network
        return json.loads(r.read())


def fetch_task_log(task_id: str, command_names: list[str]) -> str:  # pragma: no cover - network
    """Concatenate a task's per-command logs (bounded)."""
    parts: list[str] = []
    for cmd in command_names or ["main"]:
        try:
            url = LOG_URL.format(task=task_id, command=cmd)
            with urllib.request.urlopen(url, timeout=30) as r:
                parts.append(r.read().decode("utf-8", "replace"))
        except Exception:  # noqa: BLE001 - a missing per-command log is fine
            continue
    return "\n".join(parts)


# ---- pure transform (unit-tested) -----------------------------------------
def builds_to_cases(owner_repo: dict, get_log: Callable[[str, list[str]], str],
                    max_cases: int = 12) -> list[FailureCase]:
    """Turn a Cirrus GraphQL `ownerRepository` payload into FailureCases.

    `get_log(task_id, command_names) -> str` is injected so this is testable
    without the network. A task is a confirmed flake (`rerun_passed`) if another
    task with the same name on the same commit COMPLETED successfully.
    """
    builds = [e["node"] for e in owner_repo["builds"]["edges"]]
    # (task_name, sha) that succeeded somewhere -> confirmed-flake signal
    succeeded = {(t["name"], b["changeIdInRepo"])
                 for b in builds for t in b["tasks"] if t["status"] == "COMPLETED"}
    cases: list[FailureCase] = []
    for b in builds:
        for t in b["tasks"]:
            if t["status"] != "FAILED":
                continue
            cmds = [c["name"] for c in t.get("commands", [])]
            raw = get_log(t["id"], cmds)
            cases.append(FailureCase(
                run_id=b["id"], job_id=t["id"], workflow=f"cirrus/{b.get('branch', '')}",
                job_name=t["name"], head_sha=str(b["changeIdInRepo"])[:7],
                run_attempt=1,
                rerun_passed=(t["name"], b["changeIdInRepo"]) in succeeded,
                created_at=str(b.get("buildCreatedTimestamp", "")),
                excerpt=extract_failure_excerpt(raw),
            ))
            if len(cases) >= max_cases:
                return cases
    return cases


def fetch_cirrus_failed(owner: str, name: str,
                        limit: int = 5) -> list[FailureCase]:  # pragma: no cover - network
    data = cirrus_graphql(_BUILDS_QUERY, {"owner": owner, "name": name, "last": limit})
    return builds_to_cases(data["data"]["ownerRepository"], fetch_task_log)
