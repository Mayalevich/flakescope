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

    c = sub.add_parser("compare", help="run BOTH backends and report agreement")
    c.add_argument("--model", default="qwen2.5:3b")

    args = ap.parse_args(argv)

    if args.cmd == "compare":
        return _compare(args.model)

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
        print(f"  {c.job_name[:34]:36} -> {v.category:18} flake={v.is_flake} conf={v.confidence:.2f}")
    return 0


def _compare(model: str) -> int:
    """Categorize every cached case with both backends; report agreement."""
    from .categorize import categorize_heuristic, categorize_llm

    cases = load_cases()
    lines = ["# Baseline (heuristic) vs LLM", "",
             "| Job | Heuristic | LLM | Agree? |", "|---|---|---|---|"]
    agree = 0
    for c in cases:
        h = categorize_heuristic(c.excerpt)
        m = categorize_llm(c.excerpt, "ollama", model)
        ok = h.category == m.category
        agree += ok
        lines.append(f"| {c.job_name[:28]} | `{h.category}` | `{m.category}` "
                     f"| {'✅' if ok else '⚠️'} |")
        print(f"  {c.job_name[:30]:32} heuristic={h.category:16} llm={m.category:16} "
              f"{'agree' if ok else 'DIFFER'}")
    rate = agree / len(cases) if cases else 0
    lines.insert(1, f"\nModel: `{model}` · agreement with baseline: "
                    f"**{agree}/{len(cases)} ({rate:.0%})**\n")
    (OUT / "comparison.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\nagreement {agree}/{len(cases)} ({rate:.0%}) -> {OUT/'comparison.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
