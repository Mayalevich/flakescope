"""Agentic categorizer: the model navigates the log itself via tool calls.

Unlike the single-shot `categorize_llm` (which is handed a pre-extracted
excerpt), the agent starts with only the job name and must call tools
(`search_log`, `list_steps`, `read_section`) to find the failure, then `submit`.
We record the full trajectory — the tool-call sequence and step count — because
those trajectory metrics (steps-to-evidence, tool-call validity) are exactly what
this kind of assistant should be judged on.

Uses Ollama's OpenAI-style tool-calling (`/api/chat`). qwen2.5 supports tools.
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from .categorize import TAXONOMY, Verdict, _grounded
from .tools import TOOL_SCHEMAS, LogNavigator, dispatch

SKILL = (Path(__file__).resolve().parent.parent / "skills" / "ci_triage.md").read_text(
    encoding="utf-8")


@dataclass
class AgentResult:
    verdict: Verdict
    trajectory: list[str] = field(default_factory=list)   # e.g. ["search_log(FAIL)", ...]
    steps: int = 0                 # navigation tool calls before submit
    submitted: bool = False
    bytes_pulled: int = 0          # total tool-output bytes fed back to the model
    log_bytes: int = 0             # size of the full log the agent could have read
    call_errors: int = 0           # tool calls with invalid params (e.g. bad regex)

    @property
    def context_efficiency(self) -> float:
        """Fraction of the full log the agent actually pulled into context."""
        return self.bytes_pulled / self.log_bytes if self.log_bytes else 0.0

    @property
    def call_error_rate(self) -> float:
        return self.call_errors / self.steps if self.steps else 0.0


def _chat(model: str, messages: list[dict]) -> dict:
    body = json.dumps({"model": model, "messages": messages, "tools": TOOL_SCHEMAS,
                       "stream": False,
                       "options": {"temperature": 0, "seed": 0}}).encode()
    req = urllib.request.Request("http://localhost:11434/api/chat", body,
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())["message"]


def run_agent(raw_log: str, job_name: str, model: str = "qwen2.5:7b",
              max_steps: int = 6) -> AgentResult:
    nav = LogNavigator(raw_log)
    messages = [
        {"role": "system", "content": SKILL},
        {"role": "user", "content": f'Job "{job_name}" failed. Investigate with '
                                    f"tools now, then submit."},
    ]
    res = AgentResult(verdict=Verdict("unknown", False, 0.0, "", "Manual review.",
                                      f"agent:{model}"), log_bytes=len(raw_log))
    for _ in range(max_steps):
        try:
            msg = _chat(model, messages)
        except Exception as e:  # noqa: BLE001
            res.verdict.mitigation = f"agent error: {type(e).__name__}"
            return res
        calls = msg.get("tool_calls") or []
        if not calls:  # model stopped calling tools without submitting
            messages.append({"role": "user",
                             "content": "Call a tool, or submit your verdict."})
            continue
        messages.append(msg)
        for call in calls:
            fn = call["function"]["name"]
            args = fn_args(call)
            if fn == "submit":
                res.trajectory.append("submit")
                res.verdict = _finalize(args, nav, model)
                res.submitted = True
                return res
            res.steps += 1  # count navigation tool calls (not submit)
            res.trajectory.append(f"{fn}({_arg_summary(args)})")
            try:
                out = dispatch(nav, fn, args)
            except Exception as e:  # noqa: BLE001 - malformed tool args must not crash the run
                out = f"tool error: {type(e).__name__}: {e}"
            if out.startswith(("bad regex", "unknown tool", "tool error")):
                res.call_errors += 1     # invalid tool parameters
            res.bytes_pulled += len(out[:2000])
            messages.append({"role": "tool", "content": out[:2000]})
    return res


def fn_args(call: dict) -> dict:
    a = call["function"].get("arguments", {})
    if isinstance(a, dict):
        return a
    try:
        return json.loads(a or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}  # a model that emits malformed arguments must not crash the run


def _arg_summary(args: dict) -> str:
    return ",".join(f"{k}={str(v)[:20]}" for k, v in args.items())


def _finalize(args: dict, nav: LogNavigator, model: str) -> Verdict:
    cat = args.get("category") if args.get("category") in TAXONOMY else "unknown"
    ev = str(args.get("evidence", ""))[:200]
    excerpt = "\n".join(nav.lines)
    if cat != "unknown" and not _grounded(ev, excerpt):  # same grounding guard
        cat, ev = "unknown", "(evidence not found in log — refused)"
    is_flake = bool(args.get("is_flake")) and cat != "unknown"
    if cat in TAXONOMY:
        is_flake = TAXONOMY[cat][1]  # trust taxonomy over the model's boolean
    return Verdict(cat, is_flake, 0.7 if cat != "unknown" else 0.0, ev,
                   str(args.get("mitigation", "")), f"agent:{model}")
