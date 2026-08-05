# flakescope — agentic CI flake categorization (PoC)

A minimal, end-to-end prototype of the **"Agentic CI Flake Categorization and
Analysis"** idea, built and run against **real `containers/podman` GitHub Actions
failures**. It ingests failed CI runs, extracts the part of the log that actually
explains the failure, categorizes it into a flake taxonomy (flake vs real bug),
and emits a report + a PR-comment. Written as a starting point for the CNCF
Podman LFX mentorship, not a finished tool.

## Pipeline
```
GitHub Actions API ──▶ fetch.py ──▶ failure excerpt ──▶ categorize.py ──▶ report.py
 (failed runs+logs)   (extract,      (compact,          (taxonomy:        (Markdown
                       drop cleanup)   timestamp-free)    heuristic|LLM)    + PR comment)
```

## Quickstart
```bash
# 1. pull recent failed jobs for a repo (uses your `gh` auth)
python -m flakescope fetch --repo containers/podman --limit 6

# 2. categorize + report (no LLM needed — deterministic baseline)
python -m flakescope run --backend heuristic

# 3. the agentic categorizer — the model navigates the log via tool calls
#    (needs a tool-capable local model: `ollama pull qwen2.5:7b`)
python -m flakescope agent --model qwen2.5:7b

# 4. score baseline vs single-shot LLMs against the ground truth
python -m flakescope compare --models qwen2.5:3b,qwen2.5:7b
```
Outputs land in `samples/`: `flake_report.md`, `agent_report.md` (trajectories),
`comparison.md`, `sample_pr_comment.md`.

## Design choices
- **Smart excerpt, not the whole log.** CI logs run to thousands of lines; we
  anchor on real failure markers (`##[error]`, ginkgo `[FAILED]`, `Summarizing N
  Failures`) and **drop post-job cleanup noise** whose benign `Permission denied`
  lines otherwise poison the verdict. This keeps model context small — a core
  concern of the project.
- **Flake = re-run history, not a single failure.** A failure is a *confirmed*
  flake only when the same workflow passed on the same commit SHA in another run
  (`rerun_passed`); the category is only a *prior*. This is the correct domain
  model and what a Podman maintainer actually reasons about.
- **Conservative categorizer (never hide a real bug).** A genuine assertion is
  reported as a real failure unless a *strong* environment signal (connection
  refused, OOM, data race, mirror down) co-occurs — a bare `timed out` or
  `permission denied` is too ambiguous to auto-retry a real bug on.
- **Three approaches, one taxonomy.** (1) a deterministic **heuristic baseline**
  (no LLM, runs anywhere, and a yardstick to measure against); (2) a single-shot
  **LLM** handed an excerpt; (3) an **agentic** categorizer that gets only the job
  name and must call tools to find the failure itself. Comparing them is an
  evaluation habit from my retrieval work.
- **The agentic path is the point.** The agent (`flakescope/agent.py`, tools in
  `tools.py`, skill in `skills/ci_triage.md`) uses Ollama tool-calling to
  `search_log` / `list_steps` / `read_section` over a 100k+ line log, pulling only
  what it needs, then `submit`s a grounded verdict — and we record the full
  **trajectory** (tool sequence + step count), which is how such assistants should
  be judged. This mirrors the Jaeger MCP-tools + Skills design.
- **Hallucination control (from my RISC-V parameter-extraction work).** Closed-world
  (decide only from what was read), **evidence-grounded** (every verdict quotes a
  verbatim log line, verified to exist), taxonomy-constrained, temperature 0.
- **Reproducible.** Excerpts/verdicts are cached and deterministic; the ground
  truth lives in `samples/labels.json`.
## Evaluation (run for real on `ollama`, vs a hand-labeled ground truth)
Every approach is scored on the same 6 labeled cases (`samples/labels.json`) —
accuracy on the actionable **is_flake** decision and on exact **category**:

| Approach | is_flake acc | category acc | notes |
|---|---|---|---|
| heuristic baseline | 83% | **67%** | precise on formats it knows; `unknown` otherwise |
| single-shot LLM qwen2.5:3b | 50% | 0% | abstains / confabulates |
| single-shot LLM qwen2.5:7b | 50% | 0% | bigger ≠ better |
| **agentic LLM qwen2.5:7b** | **100%** | 33% | navigates the log itself (~2.8 tool calls) |

Two honest findings:

1. **Single-shot LLMs are unreliable here** — handed an excerpt, the 3B/7B models
   abstain or (with a naive prompt) confabulate a category at confidence 1.0. A
   bigger local model doesn't fix it.
2. **The agentic approach is the one that works.** Given only the job name, the
   tool-calling agent finds the failure itself in ~2.8 calls and gets the
   flake/real decision right on every labeled case — including one the regex
   baseline **missed entirely** (`sys remote`: it navigated to
   `chown: cannot access '/dev/kvm'`, which never appeared in the baseline's
   excerpt). It's still weaker than the baseline on *exact category*, so the
   right production design is a **hybrid**: the deterministic baseline for known
   formats, the agent for everything it can't parse. See `samples/agent_report.md`
   for the full trajectories and `samples/comparison.md` for the single-shot table.

This is the project's own thesis, shown with data: naive LLM use fails; the value
is in the **agentic tool-navigation + evidence grounding**, exactly what the
mentorship builds.

## Taxonomy
`network_timeout`, `timeout`, `resource_exhaustion`, `race_condition`,
`flaky_dependency`, `infra_permission` → **flake** (retry-worthy, not the code's
fault); `lint_format`, `real_test_bug` → **real** (needs a code change);
`unknown` → manual review. `is_flake` is derived from the category, and a
re-run (`run_attempt > 1`) still failing is an extra flake hint.

## Real run (this repo's `samples/`)
On 11 failed jobs from 6 recent `containers/podman` runs the baseline separates:
a `gofumpt` **lint failure** and specific ginkgo test failures (`--- FAIL:
TestMachine`, `[FAIL] Podman run networking … two static IPs`) → **likely real**;
an apt **mirror fetch failure** and a **network timeout** → **flake**; and it
honestly returns `unknown` on 3 cases. The extractor is verified to surface the
real failure line even from a **161k-line** job log (the failure sits in the
middle, not the tail).

**The `unknown` cases are the honest part.** Two are Podman **BATS** system tests
whose format (`expected exit code 0, got 28`) the Go/ginkgo-oriented regex
baseline doesn't cover; one logs its failure only to an uploaded **journal
artifact**, not stdout. These are exactly where the LLM backend (arbitrary log
formats) and artifact fetching earn their keep — the motivation for the
mentorship's agentic engine. I deliberately did **not** keep bolting on regexes
until all 11 matched: that would overfit the taxonomy to 11 samples.

## Limitations (known, on purpose)
- Category → flake is a *prior*; only `rerun_passed` is ground truth.
- Regex baseline covers common Go/ginkgo/lint/network/dependency formats; BATS
  `expected exit code` failures and journal-artifact-only failures return
  `unknown` → `needs review`.
- Ground truth is 6 hand-labeled cases — illustrative, not a benchmark.
- The agent runs on a local model (qwen2.5); a frontier model or few-shot
  prompting would likely lift its exact-category accuracy.
- Failures that live only in an uploaded journal artifact aren't fetched yet.

## What a full project adds (mentorship scope)
Already prototyped here: the agentic tool-navigation loop, re-run-based flake
confirmation, the taxonomy, and the evaluation harness. A full project would add:
- A **hybrid router** (deterministic baseline first, agent for the rest) and
  few-shot/frontier models to raise exact-category accuracy.
- **Artifact fetching** so journal-only failures become solvable.
- A larger, versioned labeled benchmark and trajectory metrics (call-error rate,
  steps-to-evidence) tracked over time.
- Workflow integration: auto-filed GitHub issues, weekly flake reports, PR
  comments, and a prompt/taxonomy operators can tune.
