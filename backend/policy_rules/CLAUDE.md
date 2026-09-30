# backend/policy_rules/ — versioned product rule sets (data)

```
policy_rules/
  term_life/v1.json   motor/v1.json   household/v1.json   (next versions: v2.json, …)
  schema/rule-file.schema.json        JSON Schema every rule file must satisfy
  PUBLISHED.lock                      append-only ledger: "<sha256>  <relative path>" per published file
```

Folder names, product codes, reason-code prefixes and the exact rule-file shape are defined in
`docs/conventions.md` → "Products and rule files". Use them verbatim.

## Rules

- Premium, eligibility, underwriting rules + reason codes, endorsement, renewal (term, grace period)
  and cancellation (refund method) rules live **here**, not in code (AC-01, AC-02).
- `status` is `DRAFT` or `PUBLISHED`. A committed PUBLISHED file is immutable — hooks
  `policy-immutability-check` (Write/Edit) and `shell-immutability-check` (Bash) block edits.
  Change rules by creating the next version with `/publish-policy-version <product>`.
- Publishing appends one line to `PUBLISHED.lock`; existing lines can never change (hook-enforced).
  The architecture test recomputes every hash and fails if a published file drifted.
- Money and rates are JSON **strings** (`"0.0125"`) so they load straight into `Decimal`.
- Every file validates against `schema/rule-file.schema.json` (skill `policy-version-validator`).
- Synthetic values only — illustrative rates, not actuarial data.
