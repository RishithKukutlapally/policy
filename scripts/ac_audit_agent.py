# /// script
# requires-python = ">=3.12"
# dependencies = ["claude-agent-sdk>=0.2"]
# ///
"""AC traceability audit driven by the Claude Agent SDK.

Step 1 (deterministic): collect every AC-NN declared in specs/*.md and every AC-NN referenced by
tests (backend/tests, e2e). Step 2 (agentic): a read-only Claude agent inspects each AC's tests and
judges whether they actually exercise the acceptance criterion, then writes
specs/reviews/ac-audit.md. Exit code 1 when any AC has no test or the agent verdict is FAIL.

Usage:  uv run scripts/ac_audit_agent.py [--no-agent]
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AC_PATTERN = re.compile(r"\bAC-(\d{2})\b")
AC_SECTION = re.compile(
    r"^##\s+Acceptance Criteria\s*$(.*?)(?=^##\s|\Z)", re.MULTILINE | re.DOTALL
)
# What counts as coverage (docs/conventions.md): the pytest marker, or AC-NN in a Playwright title.
# Each match captures the whole tag text; every AC-NN inside it counts (multi-id markers/titles).
# Matches both idioms: the `@pytest.mark.ac(...)` decorator and a module-level
# `pytestmark = pytest.mark.ac(...)` (or a list containing it).
PYTEST_MARKER = re.compile(r"pytest\.mark\.ac\(([^)]*)\)")
# Only running tests count: test(...) / test.only(...) — not test.skip / test.fixme / test.describe.
PLAYWRIGHT_TITLE = re.compile(
    r"\btest(?:\.only)?\(\s*(\"[^\"]*\"|'(?:[^'\\]|\\.)*'|`[^`]*`)"
)
TEST_SOURCES = (
    ("backend/tests/**/*.py", PYTEST_MARKER),
    ("e2e/**/*.spec.ts", PLAYWRIGHT_TITLE),
)
REPORT_PATH = REPO_ROOT / "specs" / "reviews" / "ac-audit.md"
MODEL = os.environ.get("POLICYFORGE_AGENT_MODEL", "claude-opus-5-5")


def collect_spec_acs() -> dict[str, list[str]]:
    """Map AC id -> spec files declaring it inside an '## Acceptance Criteria' section."""
    found: dict[str, list[str]] = defaultdict(list)
    for spec in sorted((REPO_ROOT / "specs").glob("*.md")):
        sections = AC_SECTION.findall(spec.read_text(encoding="utf-8"))
        for num in sorted(
            {n for section in sections for n in AC_PATTERN.findall(section)}
        ):
            found[f"AC-{num}"].append(spec.relative_to(REPO_ROOT).as_posix())
    return dict(found)


def collect_test_refs() -> dict[str, list[str]]:
    """Map AC id -> test files that tag it with the pytest marker or a Playwright title."""
    refs: dict[str, set[str]] = defaultdict(set)
    for pattern, tag in TEST_SOURCES:
        for test_file in REPO_ROOT.glob(pattern):
            if "node_modules" in test_file.parts:
                continue
            text = test_file.read_text(encoding="utf-8", errors="ignore")
            for tag_text in tag.findall(text):
                for num in AC_PATTERN.findall(tag_text):
                    refs[f"AC-{num}"].add(test_file.relative_to(REPO_ROOT).as_posix())
    return {ac: sorted(files) for ac, files in refs.items()}


def build_matrix(
    spec_acs: dict[str, list[str]], test_refs: dict[str, list[str]]
) -> str:
    rows = [
        "| AC | Declared in | Tests | Status |",
        "|----|-------------|-------|--------|",
    ]
    for ac in sorted(spec_acs):
        tests = test_refs.get(ac, [])
        status = "OK" if tests else "MISSING"
        rows.append(
            f"| {ac} | {', '.join(spec_acs[ac])} | {'<br>'.join(tests) or '—'} | {status} |"
        )
    return "\n".join(rows)


def agent_prompt(matrix: str) -> str:
    return (
        "You are auditing acceptance-criteria traceability for PolicyForge. Follow CLAUDE.md.\n"
        "Below is the deterministic AC -> test matrix. For every AC row, open the spec section and the "
        "listed tests and decide whether the tests genuinely exercise the criterion (not just mention "
        "the id). Flag weak or missing coverage with file:line evidence.\n\n"
        f"{matrix}\n\n"
        "Reply in markdown with a table (AC | Verdict STRONG/WEAK/MISSING | Evidence | Suggested test) "
        "followed by a final line exactly 'VERDICT: PASS' or 'VERDICT: FAIL'."
    )


async def run_agent(matrix: str) -> str:
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        ResultMessage,
        TextBlock,
        query,
    )

    options = ClaudeAgentOptions(
        cwd=str(REPO_ROOT),
        model=MODEL,
        allowed_tools=["Read", "Grep", "Glob"],
        disallowed_tools=[
            "Write",
            "Edit",
            "MultiEdit",
            "NotebookEdit",
            "Bash",
            "WebFetch",
            "WebSearch",
            "Task",
            "Agent",
        ],
        strict_mcp_config=True,
        max_budget_usd=2.0,
        setting_sources=["project"],
        max_turns=40,
    )
    chunks: list[str] = []
    async for message in query(prompt=agent_prompt(matrix), options=options):
        if isinstance(message, AssistantMessage):
            chunks.extend(
                block.text for block in message.content if isinstance(block, TextBlock)
            )
        elif isinstance(message, ResultMessage):
            cost = message.total_cost_usd or 0.0
            print(
                f"[ac-audit] agent finished: turns={message.num_turns} cost=${cost:.4f}"
            )
            if message.result:
                return message.result
    return "\n".join(chunks)


def final_verdict(review: str) -> str:
    """The verdict is only the reply's last non-empty line, exactly 'VERDICT: PASS|FAIL'."""
    lines = [line.strip() for line in review.strip().splitlines() if line.strip()]
    match = re.fullmatch(r"VERDICT: (PASS|FAIL)", lines[-1]) if lines else None
    return match.group(1) if match else "MISSING"


def write_report(matrix: str, agent_review: str | None, passed: bool) -> None:
    """Write the report; its last line is always the overall verdict (docs/conventions.md)."""
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    body = [
        "# AC Traceability Audit",
        "",
        "Generated by `scripts/ac_audit_agent.py`.",
        "",
        matrix,
    ]
    if agent_review:
        body += ["", "## Agent review", "", agent_review]
    body += ["", f"VERDICT: {'PASS' if passed else 'FAIL'}"]
    REPORT_PATH.write_text("\n".join(body) + "\n", encoding="utf-8")
    print(
        f"[ac-audit] report written to {REPORT_PATH.relative_to(REPO_ROOT).as_posix()}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument(
        "--no-agent", action="store_true", help="deterministic matrix only"
    )
    args = parser.parse_args()

    spec_acs = collect_spec_acs()
    if not spec_acs:
        print("[ac-audit] no AC-NN ids found under specs/", file=sys.stderr)
        return 1
    test_refs = collect_test_refs()
    matrix = build_matrix(spec_acs, test_refs)
    review = None if args.no_agent else asyncio.run(run_agent(matrix))

    missing = any(ac not in test_refs for ac in spec_acs)
    failed = review is not None and final_verdict(review) != "PASS"
    write_report(matrix, review, passed=not (missing or failed))
    return 1 if missing or failed else 0


if __name__ == "__main__":
    sys.exit(main())
