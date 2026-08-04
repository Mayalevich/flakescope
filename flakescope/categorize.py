"""Categorize a CI failure into a flake taxonomy.

Two backends behind one interface:
  - "heuristic": deterministic regex baseline. No LLM, runs anywhere. Also serves
    as the baseline to measure the LLM against (an eval habit from retrieval work).
  - "llm": an agentic categorizer (Ollama / Anthropic / OpenAI). Uses the same
    hallucination-control method as my RISC-V parameter extraction: closed-world
    (decide ONLY from the provided excerpt), evidence-grounded (quote the log
    line), taxonomy-constrained, and a fixed JSON schema.

`is_flake` is derived from the category: infra/network/race/resource/dependency
failures are flaky (not the code's fault); a genuine assertion/logic failure is
a real bug. A run_attempt > 1 that we still see failing is an extra flake hint.
"""
from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass

# Taxonomy: category -> (regex signal, is_flake, one-line meaning).
TAXONOMY: dict[str, tuple[str, bool, str]] = {
    "network_timeout": (
        r"connection refused|i/o timeout|TLS handshake|dial tcp|"
        r"could not resolve|network is unreachable|EOF\b|no route to host",
        True, "Transient network/connectivity failure.",
    ),
    "timeout": (
        r"context deadline exceeded|timed out|timeout after|deadline exceeded|"
        r"Timed out after",
        True, "Operation exceeded its time budget.",
    ),
    "resource_exhaustion": (
        r"no space left on device|cannot allocate memory|OOMKilled|"
        r"out of memory|too many open files",
        True, "Runner ran out of disk/memory/handles.",
    ),
    "race_condition": (
        r"DATA RACE|WARNING: DATA RACE|concurrent map|race detected",
        True, "Concurrency/ordering bug surfaced non-deterministically.",
    ),
    "flaky_dependency": (
        r"could not download|failed to pull|manifest unknown|"
        r"registry.*unavailable|apt-get.*failed|dnf.*failed|rate limit",
        True, "External dependency/registry was unavailable.",
    ),
    "infra_permission": (
        r"Permission denied|Operation not permitted|cannot remove|"
        r"safe\.directory|self-hosted runner",
        True, "Runner/environment/permission issue, not the test.",
    ),
    "lint_format": (
        r"not properly formatted|gofumpt|golangci-lint|goimports|"
        r"lint.*Error 1",
        False, "Code style/lint failure — a real change is needed, not a retry.",
    ),
    "real_test_bug": (
        r"Expected\b.*to (equal|be)|assertion|panic:|--- FAIL|"
        r"\[FAILED\]|should not fail|Summarizing \d+ Failure",
        False, "A genuine test assertion/logic failure.",
    ),
}

CATEGORIES = list(TAXONOMY)


@dataclass
class Verdict:
    category: str
    is_flake: bool
    confidence: float
    evidence: str        # verbatim log line(s) supporting the call
    mitigation: str
    backend: str


# Prefer an actual error line as evidence over a tool/version banner.
_STRONG = re.compile(r"error|fail|not properly|panic|timed out|refused|denied|\[FAILED\]", re.I)


def _first_match(excerpt: str, pattern: str) -> str | None:
    matches = [ln.strip() for ln in excerpt.splitlines() if re.search(pattern, ln, re.I)]
    if not matches:
        return None
    strong = [m for m in matches if _STRONG.search(m)]
    return (strong[0] if strong else matches[0])[:200]


def categorize_heuristic(excerpt: str) -> Verdict:
    """Deterministic baseline: first taxonomy pattern that matches wins.

    Order matters — infra/network signals are checked before real_test_bug so a
    cleanup 'Permission denied' doesn't get read as a genuine failure unless a
    real assertion is the only thing present.
    """
    hits: list[tuple[str, str]] = []
    for cat, (pat, _flake, _m) in TAXONOMY.items():
        ev = _first_match(excerpt, pat)
        if ev:
            hits.append((cat, ev))
    if not hits:
        return Verdict("unknown", False, 0.0, "", "Manual review required.", "heuristic")
    # Prefer a real_test_bug only if it's the sole signal; else the infra/flake one.
    non_bug = [h for h in hits if h[0] != "real_test_bug"]
    cat, ev = (non_bug[0] if non_bug else hits[0])
    is_flake, meaning = TAXONOMY[cat][1], TAXONOMY[cat][2]
    conf = 0.6 if len(hits) > 1 else 0.8
    return Verdict(cat, is_flake, conf, ev, meaning, "heuristic")


_PROMPT = """You classify a CI failure log excerpt into exactly one category.
Use ONLY the excerpt. Do not invent details not present in it.

Categories: {cats}

Return strict JSON:
{{"category": <one of the categories>,
  "confidence": <0..1>,
  "evidence": "<a verbatim line copied from the excerpt>",
  "mitigation": "<one concrete next step>"}}

EXCERPT:
{excerpt}
"""


def _ollama(excerpt: str, model: str) -> dict:
    body = json.dumps({
        "model": model,
        "prompt": _PROMPT.format(cats=", ".join(CATEGORIES), excerpt=excerpt[:6000]),
        "format": "json", "stream": False, "options": {"temperature": 0},
    }).encode()
    req = urllib.request.Request("http://localhost:11434/api/generate", body,
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(json.loads(r.read())["response"])


def categorize_llm(excerpt: str, backend: str = "ollama",
                   model: str = "qwen2.5:3b") -> Verdict:
    """Agentic/LLM categorizer. Falls back to heuristic if no backend is reachable."""
    try:
        if backend == "ollama":
            data = _ollama(excerpt, model)
        else:
            raise RuntimeError(f"backend {backend} not configured")
        cat = data["category"] if data.get("category") in TAXONOMY else "unknown"
        is_flake = TAXONOMY.get(cat, ("", False, ""))[1]
        return Verdict(cat, is_flake, float(data.get("confidence", 0.5)),
                       str(data.get("evidence", ""))[:200],
                       str(data.get("mitigation", "")), f"llm:{backend}:{model}")
    except Exception as e:  # noqa: BLE001 - PoC: any backend failure -> baseline
        v = categorize_heuristic(excerpt)
        v.backend = f"heuristic (llm fallback: {type(e).__name__})"
        return v


def categorize(excerpt: str, backend: str = "heuristic") -> Verdict:
    if backend == "heuristic":
        return categorize_heuristic(excerpt)
    return categorize_llm(excerpt, backend)
