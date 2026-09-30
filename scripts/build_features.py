"""Generate features.json from the /spec story files (harness /spec Step 6).

Every acceptance criterion in specs/stories/E*-S*.md becomes one feature entry (schema from
.claude/skills/spec/SKILL.md), so no criterion can be omitted. Writes specs/features.json and mirrors
it to the root features.json (scaffold state file used by /auto).

Usage:  uv run --no-project python scripts/build_features.py [--check]
  --check  validate only (exit 1 on problems), do not write.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STORIES_DIR = REPO_ROOT / "specs" / "stories"
OUTPUTS = (REPO_ROOT / "specs" / "features.json", REPO_ROOT / "features.json")
CATEGORIES = {"functional", "integration", "ui", "security", "performance"}

FIELD = re.compile(r"^- \*\*(?P<key>[A-Za-z ]+):\*\* (?P<value>.+)$", re.MULTILINE)
AC_SECTION = re.compile(
    r"^## Acceptance Criteria\s*$(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL
)
NUMBERED_ITEM = re.compile(r"^\d+\.\s", re.MULTILINE)
# Tag is a global AC id, an NFR id (NFR traceability), or "—" for a story-local criterion.
CRITERION = re.compile(
    r"^\d+\.\s+\[(?P<ac>AC-\d{2}|NFR-\d{2}|—)\]\s+(?P<text>.+?)\s+_\(category:\s*(?P<cat>\w+)\)_\s*\n"
    r"\s+- Verify:\s*(?P<verify>.+)$",
    re.MULTILINE,
)


@dataclass
class Criterion:
    story: str
    group: str
    ac: str
    text: str
    category: str
    steps: list[str]


def parse_story(path: Path) -> tuple[list[Criterion], list[str]]:
    text = path.read_text(encoding="utf-8")
    fields = {m["key"].strip(): m["value"].strip() for m in FIELD.finditer(text)}
    problems: list[str] = []
    story, group = fields.get("ID", ""), fields.get("Group", "")
    if story != path.stem:
        problems.append(f"{path.name}: ID '{story}' does not match file name")
    if not group:
        problems.append(f"{path.name}: missing Group")
    section_match = AC_SECTION.search(text)
    if section_match is None:
        return [], [*problems, f"{path.name}: missing '## Acceptance Criteria' section"]
    section = section_match.group(1)
    criteria = []
    for m in CRITERION.finditer(section):
        steps = [s.strip() for s in m["verify"].split(";") if s.strip()]
        criteria.append(
            Criterion(story, group, m["ac"], m["text"].strip(), m["cat"], steps)
        )
    # Every numbered item must parse — a malformed criterion must never be dropped silently.
    numbered = len(NUMBERED_ITEM.findall(section))
    if numbered != len(criteria):
        problems.append(
            f"{path.name}: {numbered} numbered criteria but {len(criteria)} match the format"
        )
    problems += validate(path.name, criteria)
    return criteria, problems


def validate(name: str, criteria: list[Criterion]) -> list[str]:
    problems = []
    if not 3 <= len(criteria) <= 6:
        problems.append(f"{name}: {len(criteria)} criteria (expected 3-6)")
    for i, c in enumerate(criteria, 1):
        if c.category not in CATEGORIES:
            problems.append(f"{name} #{i}: unknown category '{c.category}'")
        if len(c.steps) < 2:
            problems.append(f"{name} #{i}: fewer than 2 verify steps")
    return problems


def to_feature(index: int, c: Criterion) -> dict[str, object]:
    prefix = f"[{c.ac}] " if c.ac != "—" else ""
    return {
        "id": f"F{index:03d}",
        "category": c.category,
        "story": c.story,
        "group": c.group,
        "description": prefix + c.text,
        "steps": c.steps,
        "passes": False,
        "last_evaluated": None,
        "failure_reason": None,
        "failure_layer": None,
    }


def story_sort_key(path: Path) -> tuple[int, int]:
    match = re.fullmatch(r"E(\d+)-S(\d+)", path.stem)
    return (int(match.group(1)), int(match.group(2))) if match else (10**6, 10**6)


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    criteria: list[Criterion] = []
    problems: list[str] = []
    for path in sorted(STORIES_DIR.glob("E*-S*.md"), key=story_sort_key):
        found, issues = parse_story(path)
        criteria += found
        problems += issues
    for problem in problems:
        print(f"[features] {problem}", file=sys.stderr)
    if problems or not criteria:
        return 1

    features = [to_feature(i, c) for i, c in enumerate(criteria, 1)]
    acs = sorted({c.ac for c in criteria if c.ac != "—"})
    print(
        f"[features] {len(features)} features from {len({c.story for c in criteria})} stories; ACs: {', '.join(acs)}"
    )
    if not args.check:
        payload = json.dumps(features, indent=2, ensure_ascii=False) + "\n"
        for out in OUTPUTS:
            out.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
