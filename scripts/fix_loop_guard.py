"""Guardrails for the autonomous fix loop (see specs/reviews/security-review-substrate.md H1, R2-H1).

* The agent gets Read/Grep/Glob/Edit/Write plus an allow-list of test, lint and git-read commands.
* Deny rules cover protected paths and every inherited mutating/escaping command — the project
  settings re-import the harness allow-list (DEC-005) and deny beats allow.
* The loop only starts on a clean working tree; after each attempt the tamper check compares the
  tree against the recorded base commit, undoes agent commits, and restores protected paths.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

ALLOWED_TOOLS = [
    "Read",
    "Grep",
    "Glob",
    "Edit",
    "Write",
    "MultiEdit",
    "Bash(uv run pytest:*)",
    "Bash(uv run ruff:*)",
    "Bash(uv run mypy:*)",
    "Bash(uv run lint-imports:*)",
    "Bash(git diff:*)",
    "Bash(git status:*)",
]

PROTECTED_PREFIXES = (
    "backend/tests/",
    "backend/policy_rules/",
    "backend/migrations/",
    "frontend/src/__tests__/",
    "e2e/",
    "specs/",
    "docs/",
    ".claude/",
    ".github/",
    "scripts/",
)
PROTECTED_FILES = (
    "CLAUDE.md",
    "AGENTS.md",
    ".mcp.json",
    ".gitlab-ci.yml",
    "plugin.json",
    "backend/pyproject.toml",
    "backend/uv.lock",
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/vite.config.ts",
    "frontend/vitest.config.ts",
)
# Test configuration anywhere in the tree (could otherwise be used to skip or weaken tests).
PROTECTED_NAMES = ("conftest.py", "pytest.ini", ".coveragerc", "setup.cfg", "tox.ini")

_DENIED_COMMANDS = (
    "git commit",
    "git push",
    "git checkout",
    "git merge",
    "git reset",
    "git restore",
    "git stash",
    "git branch",
    "find",
    "docker",
    "gh",
    "curl",
    "rm",
    "mv",
    "cp",
    "npm",
    "npx",
)
_EDIT_TOOLS = ("Edit", "Write", "MultiEdit")

DENIED_TOOLS = [
    "WebFetch",
    "WebSearch",
    "NotebookEdit",
    "Task",
    "Agent",
    *[f"Bash({cmd}:*)" for cmd in _DENIED_COMMANDS],
    *[f"{tool}(./{prefix}**)" for tool in _EDIT_TOOLS for prefix in PROTECTED_PREFIXES],
    *[f"{tool}(./{name})" for tool in _EDIT_TOOLS for name in PROTECTED_FILES],
    *[f"{tool}(./**/{name})" for tool in _EDIT_TOOLS for name in PROTECTED_NAMES],
    *[
        f"{tool}(./**/{pattern})"
        for tool in _EDIT_TOOLS
        for pattern in (
            "test_*.py",
            "*.test.ts",
            "*.test.tsx",
            "*.spec.ts",
            "*.spec.tsx",
        )
    ],
    *[f"{tool}(./**/.env*)" for tool in (*_EDIT_TOOLS, "Read")],
]


def git(*args: str, check: bool = False) -> str:
    """Run git in the repo; with check=True a failure raises (used for state-changing calls)."""
    proc = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=check
    )
    return proc.stdout


def is_protected(rel_path: str) -> bool:
    rel = rel_path.replace("\\", "/")
    name = rel.rsplit("/", 1)[-1]
    return (
        rel.startswith(PROTECTED_PREFIXES)
        or rel in PROTECTED_FILES
        or name in PROTECTED_NAMES
        or name.startswith((".env", "test_"))
        or name.endswith((".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx"))
    )


def working_tree_clean() -> bool:
    return git("status", "--porcelain").strip() == ""


def head() -> str:
    return git("rev-parse", "HEAD").strip()


def changed_since(base: str) -> list[str]:
    """Files differing from `base` (committed or not) plus new untracked files."""
    tracked = git("diff", "--name-only", base).splitlines()
    untracked = git("ls-files", "--others", "--exclude-standard").splitlines()
    return sorted({p for p in tracked + untracked if p})


def revert_protected(base: str) -> list[str]:
    """Undo agent commits and restore protected paths to `base`; return what was touched.

    Safe only because the loop refuses to start on a dirty tree: every change since `base`
    was made by the agent.
    """
    touched: list[str] = []
    if head() != base:
        git("reset", "--mixed", base, check=True)
        touched.append("<HEAD moved: agent commits undone>")
    in_base = set(git("ls-tree", "-r", "--name-only", base).splitlines())
    for rel in (p for p in changed_since(base) if is_protected(p)):
        if rel in in_base:
            git("checkout", base, "--", rel, check=True)
        else:
            (REPO_ROOT / rel).unlink(missing_ok=True)
        touched.append(rel)
    return touched


def discard_changes(base: str) -> None:
    """Escalated run: restore the tree to `base` so unfixed code is never committed."""
    git("checkout", base, "--", ".", check=True)
    for rel in git("ls-files", "--others", "--exclude-standard").splitlines():
        (REPO_ROOT / rel).unlink(missing_ok=True)
