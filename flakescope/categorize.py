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
        r"could not resolve|network is unreachable|unexpected EOF|no route to host",
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
        r"registry.*unavailable|apt-get.*failed|dnf.*failed|rate limit|"
        r"Failed to fetch http|Unable to fetch|Could not connect to.*archive",
        True, "External dependency/registry/mirror was unavailable.",
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
    # Only genuine assertion / crash signals. A bare ginkgo "[FAILED]" is NOT
    # here: ginkgo prefixes timeouts and network errors with it too, so it is an
    # ambiguous marker, not proof of a real logic bug.
    "real_test_bug": (
        r"Expected\b.*to (equal|be|match|contain)|assertion failed|panic:|"
        r"--- FAIL|\bFAIL:\s|runtime error:|"
        r"\[FAIL\]|FAIL! -- \d+ Passed \| [1-9]",  # ginkgo spec / suite summary
        False, "A genuine test assertion/logic failure.",
    ),
}

CATEGORIES = list(TAXONOMY)

# Near-certain environment failures. Only these override a genuine assertion:
# a bare "timed out" or "permission denied" is too ambiguous to hide a real bug.
STRONG_INFRA = {"network_timeout", "resource_exhaustion", "race_condition", "flaky_dependency"}
REAL_SIGNALS = {"real_test_bug", "lint_format"}


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
    """Deterministic baseline categorizer.

    Policy (conservative — never hide a real bug behind a weak flake signal):
      * If a genuine failure (assertion / lint) is present, report THAT — unless
        a STRONG environment signal (connection refused, OOM, data race, registry
        down) co-occurs, in which case the environment most likely broke the test.
      * Otherwise take the first matching signal.
    """
    hits: dict[str, str] = {}
    for cat, (pat, _flake, _m) in TAXONOMY.items():
        ev = _first_match(excerpt, pat)
        if ev:
            hits[cat] = ev
    if not hits:
        return Verdict("unknown", False, 0.0, "", "Manual review required.", "heuristic")

    real = next((c for c in hits if c in REAL_SIGNALS), None)
    strong = next((c for c in hits if c in STRONG_INFRA), None)
    if real and not strong:
        cat = real                       # a real assertion, no strong infra -> real bug
        conf = 0.85
    elif strong:
        cat = strong                     # strong environment signal wins
        conf = 0.5 if real else 0.8      # ambiguous if a real assertion also present
    else:
        cat = next(iter(hits))           # only weak signals (bare timeout / permission)
        conf = 0.6
    is_flake, meaning = TAXONOMY[cat][1], TAXONOMY[cat][2]
    return Verdict(cat, is_flake, conf, hits[cat], meaning, "heuristic")


_PROMPT = """You classify a CI failure log excerpt into exactly one category.
Decide ONLY from the excerpt. Do not use outside knowledge or invent details.

Categories: {cats}, or "unknown".

Rules:
- If the excerpt shows no clear failure signal, answer "unknown". Do NOT guess.
- "evidence" MUST be a single line copied VERBATIM from the excerpt.

Return strict JSON:
{{"category": <a category or "unknown">,
  "confidence": <0..1>,
  "evidence": "<a verbatim line from the excerpt>",
  "mitigation": "<one concrete next step>"}}

EXCERPT:
{excerpt}
"""


def _grounded(evidence: str, excerpt: str) -> bool:
    """True if the model's evidence line really appears in the excerpt.

    Ports the evidence-grounding guard from my RISC-V extraction work: a verdict
    whose 'evidence' was invented (not in the source) is not trustworthy.
    """
    e = " ".join(evidence.split())[:40]
    return len(e) >= 8 and e in " ".join(excerpt.split())


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
                   model: str = "qwen2.5:3b", guard: bool = True) -> Verdict:
    """Agentic/LLM categorizer. Falls back to heuristic if no backend is reachable.

    With ``guard`` (default), a verdict whose evidence is not verbatim in the
    excerpt is refused to `unknown` — the confabulation guard from my RISC-V
    work. ``guard=False`` measures the raw model for comparison.
    """
    try:
        if backend == "ollama":
            data = _ollama(excerpt, model)
        else:
            raise RuntimeError(f"backend {backend} not configured")
        cat = data["category"] if data.get("category") in TAXONOMY else "unknown"
        ev = str(data.get("evidence", ""))[:200]
        conf = float(data.get("confidence", 0.5))
        if guard and cat != "unknown" and not _grounded(ev, excerpt):
            cat, conf, ev = "unknown", 0.0, "(evidence not found in excerpt — refused)"
        is_flake = TAXONOMY.get(cat, ("", False, ""))[1]
        return Verdict(cat, is_flake, conf, ev,
                       str(data.get("mitigation", "")), f"llm:{backend}:{model}")
    except Exception as e:  # noqa: BLE001 - PoC: any backend failure -> baseline
        v = categorize_heuristic(excerpt)
        v.backend = f"heuristic (llm fallback: {type(e).__name__})"
        return v


def categorize(excerpt: str, backend: str = "heuristic") -> Verdict:
    if backend == "heuristic":
        return categorize_heuristic(excerpt)
    return categorize_llm(excerpt, backend)
