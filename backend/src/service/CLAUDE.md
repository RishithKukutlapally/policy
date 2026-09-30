# backend/src/service/ — use-case orchestration

Services compose domain rules with repositories inside a single unit of work.

## Rules

- One public method per use case (`quote`, `submit_application`, `decide`, `issue_policy`, `endorse`,
  `renew`, `run_end_of_day`, `cancel`, `override_decision`, `publish_rule_version`, `portfolio_summary`).
- **Atomicity (AC-06):** a use case that writes more than one row (e.g. endorsement + policy update +
  state transition + audit) runs in one transaction — commit once at the end, roll back on any error.
- **State changes** go through `policy_state_machine.transition(...)` and append a `PolicyStateTransition`.
- **Audit (NFR-04):** every underwriter/admin action appends an `AuditRecord(actor_id, action, entity, before, after)`.
- Load rules via the config layer's rule-set loader (active PUBLISHED version); record the version used
  on quotes, decisions and policies.
- No HTTP types (Request, HTTPException) here — raise typed errors from `src.types.errors`; the API maps them.
- Log with opaque ids only (application_id, policy_number) — never PII (hook `pii-redaction-check`).
- **Rounding (NFR-01):** services never call `.quantize(`; use `src.domain.money` (`to_money`) or a domain rule (test `test_no_float_in_money.py`).
- **Ownership:** the "CUSTOMER owns it, else 404" policy guard is `src.service.ownership.owned_policy`; do not re-implement it.
