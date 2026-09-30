# Security Review — PolicyForge — scripts/build_features.py — 2026-09-29

Scope: `scripts/build_features.py` only (local dev script; no network, no subprocess, no user/HTTP input).

## Summary
- BLOCK findings: 0
- WARN findings: 0
- INFO findings: 3
- Overall verdict: CLEAR

## BLOCK Findings
None.

## WARN Findings
None.

## INFO Findings

### [INFO-001] Mild super-linear regex backtracking in CRITERION
File: scripts/build_features.py lines 26-30
Severity: INFO
Description: The lazy `text` group followed by `\s+` can overlap on whitespace. Also, `\s` matches newlines, so the `\s*\n\s+- Verify` part can span blank lines. Worst case is polynomial (about quadratic in line length) on a pathological line. It is not catastrophic/exponential, because there are no nested quantifiers. `FIELD` (line 25) is linear. The input is repo-authored markdown, so an attacker cannot exploit this.
Fix (optional): Use `[^\n]+?` for `text` and `[ \t]` in place of `\s` inside the line to keep matching single-line and linear.

### [INFO-002] Unhandled malformed story filename in story_sort_key
File: scripts/build_features.py lines 91-93
Severity: INFO
Description: The glob `E*-S*.md` also matches names with fewer than two digit groups (e.g. `E-S.md`). The two-value unpack then raises ValueError and the script crashes. This is a robustness issue, not a security one.
Fix (optional): Tighten the match to `^E\d+-S\d+$` on the stem and skip or report names that do not match.

### [INFO-003] Writes follow symlinks and are non-atomic
File: scripts/build_features.py lines 22, 119-120
Severity: INFO
Description: The output paths are fixed constants under REPO_ROOT, and no input can affect them, so path traversal is not possible. `write_text` follows a pre-existing symlink and is not atomic. Story globbing also follows symlinks. The content is serialised with `json.dumps`, so injection into the output is not possible. The data comes from specs and contains no PII or money values (NFR-01/03 not applicable).
Fix (optional): Write to a temp file and `os.replace` it into place. If you want to be strict, reject symlinked outputs.

## Delta — 2026-09-29 (regex-only changes)

- `AC_SECTION` (lines 26-28): the `(.*?)(?=^## |\Z)` lazy scan starts only at the literal `## Acceptance Criteria` anchor, and the lookahead is fixed-width. It is linear. `\Z` now captures a final section correctly. No ReDoS.
- `NUMBERED_ITEM` (line 29): `^\d+\.\s` is linear. It only counts lines that start with a number, so indented `- Verify:` lines are never counted. The count check fails closed on malformed items.
- `CRITERION` tag alternation (line 32): `AC-\d{2}|NFR-\d{2}|—` has disjoint, fixed-length branches, so it adds no backtracking. INFO-001 (quadratic worst case in `text`/`\s`, now lines 31-35) is unchanged and remains INFO.
- `story_sort_key` (lines 105-107): `re.fullmatch` on the stem with a sentinel fallback removes the unpack crash, so INFO-002 is **resolved**. A non-conforming name sorts last and is then reported by the ID/file-name check.
- No new injection, path, or I/O surface. INFO-003 is unchanged. New findings: none.

VERDICT: CLEAR
