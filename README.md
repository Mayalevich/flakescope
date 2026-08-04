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
#    or, with a local model:  ollama pull qwen2.5:3b && python -m flakescope run --backend ollama
```
Outputs land in `samples/`: `flake_report.md` and `sample_pr_comment.md`.

## Design choices
- **Smart excerpt, not the whole log.** CI logs run to thousands of lines; we
  anchor on real failure markers (`##[error]`, ginkgo `[FAILED]`, `Summarizing N
  Failures`) and **drop post-job cleanup noise** whose benign `Permission denied`
  lines otherwise poison the verdict. This keeps model context small — a core
  concern of the project.
- **Two backends behind one interface.** A deterministic **heuristic baseline**
  runs anywhere with no LLM and doubles as the yardstick to measure an LLM
  against; the **LLM backend** (Ollama today, API keys pluggable) is a one-line
  swap. Comparing model vs baseline is an evaluation habit carried over from my
  retrieval work.
- **Hallucination control (from my RISC-V parameter-extraction work).** The LLM
  prompt is **closed-world** (decide only from the excerpt), **evidence-grounded**
  (every verdict quotes a verbatim log line), **taxonomy-constrained**, and
  returns a fixed JSON schema at temperature 0.
- **Reproducible.** Excerpts are cached to `samples/failures.json` keyed by
  run/job id, so a run is deterministic and re-runnable.

## Taxonomy
`network_timeout`, `timeout`, `resource_exhaustion`, `race_condition`,
`flaky_dependency`, `infra_permission` → **flake** (retry-worthy, not the code's
fault); `lint_format`, `real_test_bug` → **real** (needs a code change);
`unknown` → manual review. `is_flake` is derived from the category, and a
re-run (`run_attempt > 1`) still failing is an extra flake hint.

## Real run (this repo's `samples/`)
On 6 recent `containers/podman` failures the baseline correctly separates a
`gofumpt` **lint failure** (real) and a ginkgo assertion (real) from macOS
machine **timeouts** (flake) — and honestly returns `unknown` on two cases where
a regex baseline has no signal. **Those `unknown` cases are exactly where the LLM
backend earns its keep** — the motivation for the mentorship's agentic engine.

## What a full project adds (mentorship scope)
- An **agentic log-navigation loop** (tool calls: list failed steps → fetch only
  the relevant section → search) instead of a fixed extractor.
- **Flake confirmation** via re-run history (failed attempt → later success on
  the same SHA).
- Workflow integration: auto-filed GitHub issues, weekly flake reports, PR
  comments, and a prompt/taxonomy operators can tune.
