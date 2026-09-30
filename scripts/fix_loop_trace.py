"""Fix-loop trace model and markdown rendering (canonical template, docs/conventions.md)."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field


@dataclass
class Attempt:
    number: int
    agent_summary: str
    validation_output: str
    passed: bool
    tampered: list[str] = field(default_factory=list)


@dataclass
class Trace:
    slug: str
    test_cmd: str
    workdir: str
    branch: str
    base: str = ""
    detection_output: str = ""
    attempts: list[Attempt] = field(default_factory=list)

    @property
    def fixed(self) -> bool:
        return bool(self.attempts) and self.attempts[-1].passed


def _fenced(text: str) -> list[str]:
    return ["```", text.strip(), "```"]


def render_attempt(attempt: Attempt) -> list[str]:
    verdict = "PASS" if attempt.passed else "FAIL"
    lines = [
        "",
        f"## 2.{attempt.number} Reproduce + fix (attempt {attempt.number})",
        attempt.agent_summary.strip() or "_no summary returned_",
    ]
    if attempt.tampered:
        lines += [
            "",
            f"**Tamper check:** reverted {attempt.tampered} — attempt failed.",
        ]
    lines += [
        "",
        f"## 3.{attempt.number} Validate — {verdict}",
        *_fenced(attempt.validation_output),
    ]
    return lines


def render_trace(trace: Trace, diff_stat: str) -> str:
    lines = [
        f"# Fix loop — {trace.slug}",
        "",
        f"- **Date:** {dt.datetime.now(dt.UTC).isoformat(timespec='seconds')}",
        f"- **Status:** {'FIXED' if trace.fixed else 'ESCALATED'}",
        f"- **Branch:** `{trace.branch}` (base `{trace.base[:10]}`)",
        f"- **Command:** `cd {trace.workdir} && {trace.test_cmd}`",
        "",
        "## 1. Detect",
        *_fenced(trace.detection_output),
    ]
    for attempt in trace.attempts:
        lines += render_attempt(attempt)
    lines += ["", "## 4. Change set", *_fenced(diff_stat or "(no changes)"), ""]
    lines += [
        "## 5. PR",
        f"Merge with `/sprint-close` or `git merge --no-ff {trace.branch}`.",
        "",
    ]
    return "\n".join(lines)
