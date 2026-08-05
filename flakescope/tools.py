"""Tools the agent uses to navigate a CI job log itself.

The whole point of the agentic path: the model is NOT handed the log. It must
call these tools to explore a 100k+ line log, pulling only what it needs — which
is how you keep context small and how a real MCP-style assistant works. Every
tool returns a bounded result.
"""
from __future__ import annotations

import re

_TS = re.compile(r"^\S+Z\s")
_GROUP = re.compile(r"##\[group\](.*)")
_CLEANUP = re.compile(r"Post[- ]job cleanup|Cleaning up orphan processes", re.I)


def _strip(line: str) -> str:
    return _TS.sub("", line)


class LogNavigator:
    """Bounded read-only tools over one job log."""

    def __init__(self, raw: str):
        lines = raw.splitlines()
        for i, ln in enumerate(lines):  # ignore teardown noise
            if _CLEANUP.search(ln):
                lines = lines[:i]
                break
        self.lines = lines

    def list_steps(self) -> str:
        """List the job's step/group names with their line numbers."""
        out = []
        for i, ln in enumerate(self.lines):
            m = _GROUP.search(ln)
            if m:
                out.append(f"L{i}: {_strip(m.group(1)).strip()[:80]}")
        if not out:
            return f"(no step groups; log has {len(self.lines)} lines)"
        return "\n".join(out[:60])

    def search_log(self, pattern: str, max_results: int = 15) -> str:
        """Return log lines (with line numbers) matching a regex."""
        try:
            rx = re.compile(pattern, re.I)
        except re.error as e:
            return f"bad regex: {e}"
        hits = [f"L{i}: {_strip(ln).strip()[:200]}"
                for i, ln in enumerate(self.lines) if rx.search(ln)]
        if not hits:
            return "(no matches)"
        return "\n".join(hits[:max_results]) + (
            f"\n... (+{len(hits) - max_results} more)" if len(hits) > max_results else "")

    def read_section(self, start: int, end: int) -> str:
        """Read log lines [start, end) — capped at 120 lines."""
        start = max(0, int(start))
        end = min(len(self.lines), max(start + 1, int(end)), start + 120)
        return "\n".join(f"L{i}: {_strip(self.lines[i]).rstrip()[:200]}"
                         for i in range(start, end)) or "(empty)"


# Ollama/OpenAI-style tool schemas the model sees.
TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "list_steps", "description": "List the job's step/group names and line numbers.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "search_log",
        "description": "Search the log for a regex (e.g. 'FAIL|panic|Error'). Returns matching lines with line numbers.",
        "parameters": {"type": "object", "properties": {
            "pattern": {"type": "string"}}, "required": ["pattern"]}}},
    {"type": "function", "function": {
        "name": "read_section", "description": "Read a slice of the log by line range.",
        "parameters": {"type": "object", "properties": {
            "start": {"type": "integer"}, "end": {"type": "integer"}},
            "required": ["start", "end"]}}},
    {"type": "function", "function": {
        "name": "submit",
        "description": "Submit the final verdict once you have found the failure.",
        "parameters": {"type": "object", "properties": {
            "category": {"type": "string"},
            "is_flake": {"type": "boolean"},
            "evidence": {"type": "string", "description": "verbatim log line"},
            "mitigation": {"type": "string"}},
            "required": ["category", "is_flake", "evidence"]}}},
]


def dispatch(nav: LogNavigator, name: str, args: dict) -> str:
    if name == "list_steps":
        return nav.list_steps()
    if name == "search_log":
        return nav.search_log(str(args.get("pattern", "")))
    if name == "read_section":
        return nav.read_section(args.get("start", 0), args.get("end", 0))
    return f"unknown tool {name}"
