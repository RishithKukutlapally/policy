# Clean Code Review — chore/policyforge-substrate (scripts/build_features.py) — 2026-09-29
Counts: high 0 · medium 2 · low 4
Tool results: ruff ✓ (per author; uv not on reviewer PATH) · mypy --strict ✓ (per author) · lint-imports n/a · arch tests n/a
Scope: scripts/build_features.py only. All functions < 50 lines (longest `main` ~26), file 126 lines, nesting <= 3, params <= 2, fully annotated, no `Any`.
Note: specs/stories/ currently has no E*-S*.md files, so the parser was reviewed against its regexes, not real stories.

## High
(none)

## Medium
- [CC-001] scripts/build_features.py:54 — Criteria that don't match CRITERION exactly (for example a missing `- Verify:` line, a Verify line that is not directly after its item, or a missing `_(category: x)_` suffix) are skipped without any warning. The only safeguard is the 3-6 count check, so a story with 7 items where 4 parse still passes and 3 acceptance criteria disappear from features.json. That breaks the "no criterion can be omitted" promise in the docstring. Fix: count the numbered items in the section with `^\d+\.\s` and report a problem when that count differs from the number of CRITERION matches.
- [CC-002] scripts/build_features.py:52 — `split("## Acceptance Criteria", 1)[-1]` falls back to the whole file when the heading is missing, and it never stops at the next `## ` heading. Numbered lists in later sections (Notes, Out of scope) can then be picked up. Fix: report a problem when the heading is absent, and cut the section at the next `^## ` line.

## Low
- [CC-003] scripts/build_features.py:27,76,113 — The em-dash "no AC" marker `"—"` is repeated as a magic string in 3 places. Fix: add a module constant `NO_AC = "—"`.
- [CC-004] scripts/build_features.py:92 — Unpacking `[:2]` raises `ValueError` on a stem such as `E1-Sx.md` that the glob still matches. Fix: use a regex like `^E(\d+)-S(\d+)$` and report a problem for names that don't match.
- [CC-005] scripts/build_features.py:55 — Verify steps are split on `;`, so a single step that contains a semicolon becomes two steps. Fix: document the rule in the story template, or use a separator that won't appear in step text.
- [CC-006] scripts/build_features.py:119-120 — The two output files are written one after the other and not atomically, so a failure part-way leaves specs/features.json and features.json out of sync. Fix: write to a temp file, then `replace()`. Minor for a dev script.

## Delta — 2026-09-29
Re-reviewed scripts/build_features.py (139 lines, all functions < 50 lines, fully typed). `--check` run by reviewer: exit 0, 87 features from 17 stories (the author reported 13 files; 4 more stories have been added since).
- CC-001 resolved: scripts/build_features.py:67-72. Probe: 4 numbered items with 1 malformed produced the problem '4 numbered criteria but 3 match the format'.
- CC-002 resolved: scripts/build_features.py:26-28,58-59. A missing heading is reported. The section ends at the next `## ` heading but keeps `### ` subsections. Numbered items under a later `## Notes` heading were ignored in the probe.
- CC-004 resolved: scripts/build_features.py:105-107. The fullmatch fallback sorts names like `E1-Sx` last with no crash, and the ID-vs-stem check at :53 still reports them.
- Tag widening to AC-NN|NFR-NN|— is correct. `to_feature` and the AC summary exclude only `—`.
- Still open (low): CC-003 (the `—` magic string is now at :32,:90,:127), CC-005, CC-006. Also new low CC-007 at :68: a numbered line at column 0 inside a fenced code block in the section would be counted. This is acceptable, because it can only fail loudly and never drops a criterion.
Counts after delta: high 0 · medium 0 · low 4

VERDICT: APPROVE_WITH_NITS
