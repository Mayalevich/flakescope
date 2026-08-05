"""CLI: python -m flakescope <fetch|run> [options].

  fetch  — pull recent failed runs for a repo and cache failure excerpts
  run    — categorize cached failures and write a Markdown report
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .categorize import categorize
from .fetch import cache_cases, fetch_failed, load_cases
from .report import markdown_report, pr_comment

OUT = Path(__file__).resolve().parent.parent / "samples"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="fetch failed runs -> samples/failures.json")
    f.add_argument("--repo", default="containers/podman")
    f.add_argument("--limit", type=int, default=5)

    r = sub.add_parser("run", help="categorize cached failures -> report")
    r.add_argument("--backend", default="heuristic",
                   choices=["heuristic", "ollama"],
                   help="heuristic (no LLM, runs anywhere) or ollama (local LLM)")

    c = sub.add_parser("compare", help="score baseline + LLM(s) vs ground truth")
    c.add_argument("--models", default="qwen2.5:3b",
                   help="comma-separated Ollama models")

    a = sub.add_parser("agent", help="run the agentic categorizer (tool-calling) on all cases")
    a.add_argument("--model", default="qwen2.5:7b")

    args = ap.parse_args(argv)

    if args.cmd == "compare":
        return _compare([m.strip() for m in args.models.split(",") if m.strip()])
    if args.cmd == "agent":
        return _agent(args.model)

    if args.cmd == "fetch":
        cases = fetch_failed(args.repo, args.limit)
        path = cache_cases(cases)
        print(f"cached {len(cases)} failed jobs -> {path}")
        return 0

    cases = load_cases()
    rows = [(c, categorize(c.excerpt, args.backend)) for c in cases]
    (OUT / "flake_report.md").write_text(markdown_report(rows), encoding="utf-8")
    (OUT / "sample_pr_comment.md").write_text(
        pr_comment(*rows[0]) if rows else "no cases", encoding="utf-8")
    print(f"wrote {OUT/'flake_report.md'} ({len(rows)} cases, backend={args.backend})")
    for c, v in rows:
        print(f"  {c.job_name[:34]:36} -> {v.category:18} "
              f"flake={v.is_flake} conf={v.confidence:.2f}")
    return 0


def _accuracy(verdicts: dict[int, tuple[str, bool]], labels: dict) -> tuple[float, float, int]:
    """(category accuracy, is_flake accuracy, n) over the labeled cases."""
    cat_ok = flake_ok = n = 0
    for jid, lab in labels.items():
        if not jid.isdigit() or int(jid) not in verdicts:
            continue
        n += 1
        cat, is_flake = verdicts[int(jid)]
        cat_ok += cat == lab["category"]
        flake_ok += is_flake == lab["is_flake"]
    return (cat_ok / n if n else 0.0), (flake_ok / n if n else 0.0), n


def _compare(models: list[str]) -> int:
    """Score the heuristic baseline and each LLM against the ground-truth labels."""
    import json

    from .categorize import categorize_heuristic, categorize_llm

    cases = load_cases()
    labels = json.loads((OUT / "labels.json").read_text(encoding="utf-8"))

    backends: dict[str, dict[int, tuple[str, bool]]] = {
        "heuristic": {c.job_id: (v.category, v.is_flake)
                      for c in cases for v in [categorize_heuristic(c.excerpt)]}
    }
    for i, model in enumerate(models):
        backends[f"{model}"] = {
            c.job_id: (v.category, v.is_flake)
            for c in cases for v in [categorize_llm(c.excerpt, "ollama", model, guard=True)]
        }
        if i == 0:  # also measure the first model WITHOUT the grounding guard
            backends[f"{model} (raw)"] = {
                c.job_id: (v.category, v.is_flake)
                for c in cases for v in [categorize_llm(c.excerpt, "ollama", model, guard=False)]
            }

    lines = ["# Baseline vs LLM — accuracy on hand-labeled ground truth", "",
             "| Backend | is_flake acc | category acc | (n labeled) |",
             "|---|---|---|---|"]
    print("Accuracy on labeled ground truth:")
    for name, verdicts in backends.items():
        cat_acc, flake_acc, n = _accuracy(verdicts, labels)
        lines.append(f"| `{name}` | {flake_acc:.0%} | {cat_acc:.0%} | {n} |")
        print(f"  {name:16} is_flake={flake_acc:.0%}  category={cat_acc:.0%}  (n={n})")

    # Full per-case table for transparency.
    lines += ["", "## Per-case", "",
              "| Job | " + " | ".join(backends) + " | truth |",
              "|---|" + "---|" * (len(backends) + 1)]
    for c in cases:
        truth = labels.get(str(c.job_id), {}).get("category", "—")
        cells = " | ".join(f"`{backends[b][c.job_id][0]}`" for b in backends)
        lines.append(f"| {c.job_name[:26]} | {cells} | {truth} |")
    (OUT / "comparison.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\n-> {OUT/'comparison.md'}")
    return 0


def _agent(model: str) -> int:
    """Run the tool-calling agent on every case; record trajectories + metrics."""
    import json

    from .agent import run_agent
    from .categorize import categorize_heuristic
    from .fetch import load_raw

    cases = load_cases()
    labels = json.loads((OUT / "labels.json").read_text(encoding="utf-8"))
    intro = (f"Model: `{model}`. The agent gets only the job name and must call "
             "tools to find the failure itself.")
    lines = ["# Agentic categorizer (tool-calling) — trajectories & metrics", "",
             intro, "",
             "| Job | Verdict | Steps | Ctx% | Trajectory | Evidence |",
             "|---|---|---|---|---|---|"]
    # accuracy accumulators (agent + hybrid), keyed on the labeled subset
    a_cat = a_flake = h_cat = h_flake = n = 0
    steps = errs = pulled = logbytes = submitted = 0
    for c in cases:
        try:
            r = run_agent(load_raw(c.job_id), c.job_name, model)
        except FileNotFoundError:
            continue
        heur = categorize_heuristic(c.excerpt)
        hybrid = heur if heur.category != "unknown" else r.verdict  # heuristic first
        submitted += r.submitted
        steps += r.steps
        errs += r.call_errors
        pulled += r.bytes_pulled
        logbytes += r.log_bytes
        traj = " → ".join(r.trajectory).replace("|", "\\|")[:60]
        lines.append(f"| {c.job_name[:24]} | `{r.verdict.category}` "
                     f"{'🟡' if r.verdict.is_flake else '🔴'} | {r.steps} "
                     f"| {r.context_efficiency*100:.2f} | {traj} "
                     f"| {r.verdict.evidence[:44].replace('|','')} |")
        print(f"  {c.job_name[:26]:28} {r.verdict.category:15} steps={r.steps} "
              f"ctx={r.context_efficiency*100:.2f}% traj={' → '.join(r.trajectory)[:48]}")
        lab = labels.get(str(c.job_id))
        if lab:
            n += 1
            a_cat += r.verdict.category == lab["category"]
            a_flake += r.verdict.is_flake == lab["is_flake"]
            h_cat += hybrid.category == lab["category"]
            h_flake += hybrid.is_flake == lab["is_flake"]

    nz = len(cases) or 1
    metrics = [
        "", "## Trajectory metrics (from the real runs)",
        f"- **{submitted}/{len(cases)} submitted** a verdict",
        f"- **steps-to-evidence:** {steps/nz:.1f} tool calls/case (avg)",
        f"- **call-error rate:** {errs/steps if steps else 0:.0%} (invalid tool params)",
        f"- **context efficiency:** agent pulled **{pulled/logbytes*100 if logbytes else 0:.2f}%** "
        f"of the total log into context ({pulled/1024:.0f} KB of {logbytes/1024/1024:.1f} MB)",
    ]
    if n:
        metrics += [
            "", f"## Accuracy on {n} labeled cases",
            "| Approach | is_flake | category |", "|---|---|---|",
            f"| agent (`{model}`) | {a_flake/n:.0%} | {a_cat/n:.0%} |",
            f"| **hybrid (heuristic→agent)** | **{h_flake/n:.0%}** | **{h_cat/n:.0%}** |",
        ]
    lines[3:3] = metrics
    (OUT / "agent_report.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(m for m in metrics if m and not m.startswith("|")))
    print(f"-> {OUT/'agent_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
