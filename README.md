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
- **Flake = re-run history, not a single failure.** A failure is a *confirmed*
  flake only when the same workflow passed on the same commit SHA in another run
  (`rerun_passed`); the category is only a *prior*. This is the correct domain
  model and what a Podman maintainer actually reasons about.
- **Conservative categorizer (never hide a real bug).** A genuine assertion is
  reported as a real failure unless a *strong* environment signal (connection
  refused, OOM, data race, mirror down) co-occurs — a bare `timed out` or
  `permission denied` is too ambiguous to auto-retry a real bug on.
- **Two backends behind one interface.** A deterministic **heuristic baseline**
  runs anywhere with no LLM and doubles as the yardstick to measure an LLM
  against; the **LLM backend** is a one-line swap. Comparing model vs baseline is
  an evaluation habit carried over from my retrieval work.
  > **Run for real (`qwen2.5:3b` via Ollama).** `python -m flakescope compare`
  > categorizes all 11 cases with both backends: **agreement 4/11 (36%)**. The
  > telling part is *how* they differ — the 3B model **never abstains**. On the
  > cases the baseline honestly returns `unknown`, the model confabulates a
  > category (it labeled an artifact-upload failure and a `curl` timeout as
  > `lint_format`) and reports confidence 1.0. That empirically reproduces the
  > hallucination problem my RISC-V extraction work targets, and is precisely the
  > small-model reliability question this project must answer — evidence
  > grounding and forced abstention matter more than raw model size. See
  > `samples/comparison.md`.
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
- The LLM backend is implemented but not yet run on a live model (see above).
- One representative excerpt per failed job; artifact logs are not fetched yet.

## What a full project adds (mentorship scope)
- An **agentic log-navigation loop** (tool calls: list failed steps → fetch only
  the relevant section → search) instead of a fixed extractor.
- **Flake confirmation** via re-run history (failed attempt → later success on
  the same SHA).
- Workflow integration: auto-filed GitHub issues, weekly flake reports, PR
  comments, and a prompt/taxonomy operators can tune.
