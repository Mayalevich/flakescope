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

    args = ap.parse_args(argv)

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


if __name__ == "__main__":
    raise SystemExit(main())
