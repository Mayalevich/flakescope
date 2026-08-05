# flakescope — agentic CI flake categorization (PoC)

[![CI](https://github.com/Mayalevich/flakescope/actions/workflows/ci.yml/badge.svg)](https://github.com/Mayalevich/flakescope/actions/workflows/ci.yml)

A minimal, end-to-end prototype of the **"Agentic CI Flake Categorization and
Analysis"** idea, built and run against **real `containers/podman` GitHub Actions
failures**. It ingests failed CI runs, extracts the part of the log that actually
explains the failure, categorizes it into a flake taxonomy (flake vs real bug),
and emits a report + a PR-comment. Written as a starting point for the CNCF
Podman LFX mentorship, not a finished tool.

## Why this matches Podman's real flake problem
Grounded in how the Podman maintainers actually describe flakes
([containers/podman#17967](https://github.com/containers/podman/issues/17967)):
- **Their taxonomy is essentially this one.** They bucket e2e flakes into
  (1) resource/network/registry, (2) *real Podman bugs*, (3) test-infra bugs
  (races, insufficient locking) — which maps to `flaky_dependency`/`network_*`,
  `real_test_bug`, and `race_condition` here.
- **"Hiding flakes with retries also hides real Podman bugs"** (the sqlite case) —
  that quote is exactly why this tool is **conservative**: it will not label a
  genuine assertion a flake, so a real bug never gets auto-retried away.
- **The gap it fills:** Podman's existing flake logging only captures the
  triple-failures that force a manual re-run; single failures "happen every day …
  and we're just not seeing them." This tool categorizes **every** failure it
  ingests, not only the triple-fails.
- **Relation to existing tooling.** Podman's CI automation
  ([`containers/automation`](https://github.com/containers/automation)) is Python
  and **Cirrus-centric** (`cirrus-ci_retrospective`, `cirrus-task-map`, …), and
  flakes are tracked on Cirrus (e.g. Ed Santiago's `cirrus-flake-xref`, which
  *logs/cross-references* recurring flakes). This PoC is deliberately
  complementary: same language (Python), it targets the **GitHub Actions** logs
  the mentorship scopes, and it adds the LLM/agentic **root-cause categorization**
  layer that doesn't exist yet — not just logging. Extending ingestion to Cirrus
  is the natural next step.

**Validated against real flakes (and two honest gaps).** I bucketed Podman's
real `flakes` / `kind/test-flake` issues against this taxonomy. It covers the
network/registry, resource (`Resource temporarily unavailable`), real-test-bug,
and timeout/hang classes well. Two gaps it does *not* cover cleanly:
1. **Machine/VM-startup flakes** (`wsl` / `windows machine` / `applehv`) — a whole
   recurring class with no clean bucket (the ambiguous cases I left unlabeled).
2. **The dominant race/locking class.** Maintainers say most flakes are test-infra
   races; but real ones surface as *varied symptoms* (`unlinkat EBUSY`, `container
   does not exist`, `send on closed channel`, locking) that a symptom regex like
   `race_condition` mostly misses. The lesson: that class is best caught **not by
   log symptoms but by re-run history** — precisely what `rerun_passed` does. So
   the re-run signal matters more than symptom matching for Podman's #1 flake type.

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
Scored on **8 labeled cases** (`samples/labels.json`; ambiguous cases left
unlabeled on purpose). **These numbers are illustrative, not a benchmark — at
n = 8, one case is ~12 pp**, so lean on the *qualitative* findings below, not the
decimals.

| Approach | is_flake | category | reproducible? |
|---|---|---|---|
| heuristic baseline | 88% | 75% | fully (deterministic) |
| single-shot LLM qwen2.5:7b | 62% | 12% | yes (`seed=0`) |
| agentic LLM qwen2.5:7b | 75% | 62% | approx (`seed=0`; tool-calling still varies) |
| **hybrid (heuristic → agent)** | **100%** | **88%** | approx |

**Agent trajectory metrics** (measured, not asserted): **11/12** submitted a
verdict · **2.2** tool calls to evidence (avg) · **0%** call-error rate ·
**context efficiency ~1.5%** — the agent pulled **~33 KB of the log corpus** into
context per case. Reading a fraction of the log is the point of the agentic path.

What's actually true (and what isn't):

1. **The single-shot LLM is worse than a regex on the *same* excerpt** (12% vs the
   heuristic's 75% category). So this isn't "LLMs are magic" — a plain LLM
   underperforms deterministic rules here.
2. **The agent is a *complement*, not a better categorizer.** Its category
   accuracy (62%) is *below* the heuristic's (75%) — it over-guesses on ambiguous
   machine tests. Its real value is narrow but real: it reads logs the regex can't
   parse (it navigated to `chown: cannot access '/dev/kvm'`, a case the baseline
   missed) and it decides flake-vs-real, cheaply (~1.5% of the log).
3. **The hybrid is the right design** — heuristic first, agent on what it can't
   parse: **88% category / 100% is_flake**, above either alone.
4. **Re-run history is the real flake signal, and it fired:** **3 of 12** cases
   are confirmed flakes (the same commit passed on another run) — ground truth,
   not a guessed category.
5. **Honest negative result:** removing the search hint from the skill to make the
   agent *fully* autonomous **degraded** the 7B model (it chose narrower patterns
   and missed signals). The hint is load-bearing for a small local model;
   genuinely autonomous search needs a stronger model. So the shipped skill keeps
   a light hint — chosen on evidence, not vibes.

Caveats kept in view: n = 8; the taxonomy is Podman/ginkgo-tuned (two unlabeled
cases — a VM-boot failure and a docs-xref check — don't fit it cleanly); the
few-shot examples in `skills/ci_triage.md` are **generic** (not any labeled
case's evidence), so gains are generalization, not leakage.

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

## CI integration (runnable, in this repo)
- `.github/workflows/ci.yml` — real CI: `ruff` + `pytest` on 3.11/3.12.
- `.github/workflows/flakescope.yml` — triggers **when CI fails** (and on demand),
  runs flakescope on this repo's own failures with the no-LLM heuristic backend,
  and publishes the flake report to the run's **job summary** + an artifact. This
  is the closed loop the mentorship targets — CI fails → it gets triaged
  automatically — using the deterministic path that needs no model in CI.
  (Verified live: a failing CI run triggered the triage, which ran and posted a
  report. Amusingly, when flakescope triages its *own* lint failure, ruff echoes
  flakescope's source — including its taxonomy regexes — so it matches its own
  patterns; a self-reference artifact that doesn't occur on real target repos.
  The curated real-data results above come from `containers/podman`.)

## Limitations (known, on purpose)
- Category → flake is a *prior*; only `rerun_passed` is ground truth.
- Regex baseline covers common Go/ginkgo/lint/network/dependency formats; BATS
  `expected exit code` failures and journal-artifact-only failures return
  `unknown` → `needs review`.
- Ground truth is 8 hand-labeled cases — illustrative, not a benchmark. Genuinely
  ambiguous cases are left unlabeled rather than guessed.
- The agent runs on a local model (qwen2.5:7b); a frontier model would likely lift
  its exact-category accuracy further (few-shot already helped, see above).
- Failures that live only in an uploaded journal artifact aren't fetched yet.
- The agent eval is reproducible from a clone: the 8 labeled cases' raw logs are
  committed gzipped (`samples/raw_*.log.gz`); `load_raw` reads them transparently.
- **Heuristic false-positive on benign keywords.** The regex matches a
  failure-signal string even in a *passing* context (a test literally named
  `... connection refused ...`, an expected-error message), so it can mislabel.
  Bounded in practice — only GitHub-failed jobs are categorized and extraction
  centers on the real failure anchor — but a mixed log can still fool the regex.
  The LLM/agent reads context and is more robust here (found via an adversarial
  no-failure-log test); one more reason the hybrid beats regex alone.

## What a full project adds (mentorship scope)
Already prototyped here: the agentic tool-navigation loop, the measured hybrid
router, re-run-based flake confirmation, the taxonomy, trajectory metrics, and
the evaluation harness. A full project would add:
- Few-shot / frontier models to raise the agent's exact-category accuracy above
  the current 33% (the hybrid already reaches 83%).
- **Artifact fetching** so journal-only failures become solvable.
- A larger, versioned labeled benchmark and trajectory metrics (call-error rate,
  steps-to-evidence) tracked over time.
- Workflow integration: auto-filed GitHub issues, weekly flake reports, PR
  comments, and a prompt/taxonomy operators can tune.
