# PolicyForge — Business Case

**Business case:** BC-AINE-004 · Policy Issuance & Lifecycle Management Platform
**Client:** Horizon Insurance (fictional) · General and Life insurance
**Sources:** capstone brief §3 and §6, approved BRD `specs/brd/brd.md` (2026-09-29)

---

## 1. The problem

Horizon Insurance sells three lines of cover — **term life, motor and household** — but administers
them through disconnected, largely manual processes. The consequences are felt at every step of a
policy's life:

- **Pricing is inconsistent.** Two staff members can quote the same risk differently, and nobody can
  reliably reproduce last month's price because the rules in force are not recorded with the quote.
- **Change is expensive.** A new rate table or eligibility rule needs a developer and a release, so
  product teams wait weeks for simple adjustments.
- **Decisions are not traceable.** Underwriting outcomes and overrides are not tied to the rule set that
  produced them or to the person who made them, which is an audit and compliance exposure.
- **The back half of the lifecycle is ad hoc.** Endorsements, renewals, lapses for non-payment and
  cancellations are handled case by case, producing premium and refund errors and no dependable history.
- **Personal data leaks into operations.** Identity numbers and health answers end up in logs and
  spreadsheets.

Doing nothing means slower sales, financial leakage from mis-priced policies and wrong refunds, rising
compliance risk, and engineering capacity spent on routine rate changes.

## 2. Who it is for

| User | What they need from PolicyForge |
|------|---------------------------------|
| **Customers** | A quick, consistent quote; a simple application with a basic identity (KYC) step; a clear view of their policies, due dates and history; self-service changes, renewal and cancellation with a transparent refund |
| **Underwriters** | A queue of cases that need human judgement, the full case detail, and a way to approve or decline with standard reason codes |
| **Administrators** | Control of the product catalogue and its rule versions without developers, the power to override a decline with a recorded justification, and a portfolio view of the business |
| **Operations (system)** | A reliable end-of-day run that renews due policies and lapses unpaid ones exactly once |

## 3. The solution

PolicyForge is one platform for the **whole policy lifecycle** — quote, application, underwriting,
issuance, endorsement, renewal, lapse and cancellation — for all three products.

The central idea is that **every business rule is data, versioned and immutable once published**. Each
product has a rule set (rates, rating factors, eligibility limits, underwriting thresholds and reason
codes, endorsement options, renewal term and grace period, refund method). Administrators publish a new
version to change the business; the old version stays untouched, so every quote, decision and policy can
be explained and reproduced from the exact version that produced it.

## 4. Domain rules the platform enforces

1. **Deterministic pricing** — the same product, risk inputs and rule version always give the same
   premium, computed in fixed-point decimal and rounded half-up to the paisa; never floating point.
2. **Three distinct products** — term life, motor and household each have their own rule set.
3. **Validated applications** — risk inputs and the KYC stub are checked against the product's rules
   before a case reaches underwriting.
4. **Explainable underwriting** — every case is auto-bound, sent for manual review, or declined, always
   with reason codes taken from the active rule version.
5. **Controlled issuance** — an issued policy gets a unique number, effective date, sum insured and
   premium, and starts ACTIVE.
6. **Safe policy changes** — an endorsement creates a permanent record and updates the policy in a single
   all-or-nothing step.
7. **Renewal and lapse** — due policies renew into a new term at a refreshed premium; a policy whose
   premium stays unpaid past the grace period lapses automatically.
8. **Fair cancellation** — a cancelled policy earns a pro-rated refund according to its product's rules,
   recorded permanently.
9. **Accountable overrides** — only an administrator can overturn a decline, and must give a reason code
   and comment; the override is audited.
10. **A strict lifecycle** — policies move ACTIVE → ENDORSED / LAPSED / CANCELLED / RENEWED only along
    allowed paths; anything else is rejected.
11. **Nothing is rewritten** — rule versions, endorsements, state changes, payments, refunds and audit
    entries are append-only.
12. **Privacy by default** — Aadhaar, PAN and health declarations never appear in logs and are masked on
    screen; all demonstration data is synthetic.

## 5. Success metrics

| Metric | Target |
|--------|--------|
| Quote response time | under 2 seconds |
| Quote reproducibility | 100 % — same input and rule version, same premium |
| Straight-through processing | at least 70 % of applications auto-bound |
| Time to change a rate or rule | a published rule version, zero code changes |
| Audit coverage of underwriter and admin actions | 100 %, with the acting user recorded |
| Personal data in logs | zero occurrences |
| Renewal and lapse processing | runs daily with no duplicate renewals or lapses |
| Engineering quality | ≥ 80 % automated test coverage; every acceptance criterion has a test |

## 6. Value proposition

- **For customers:** fast, consistent quotes and self-service changes with transparent refunds.
- **For underwriters:** time spent only on cases that genuinely need judgement, with the reasons in front of them.
- **For the business:** rate and rule changes in minutes instead of release cycles; fewer premium and
  refund errors; renewals and lapses handled automatically.
- **For risk and compliance:** every price and decision is reproducible from its rule version, every
  override is attributable, history cannot be altered, and personal data stays out of logs.

## 7. Scope boundaries

Included: the three products, the full policy lifecycle, the underwriter workbench, the product catalogue
manager, the renewal scheduler and the admin portfolio dashboard.

Not included: real identity-document verification, credit bureau / health / vehicle record integrations,
a real payment gateway (payments are simulated), reinsurance, distribution channels and broker
commission, and production hosting concerns (secrets, multi-region, distributed locking).

## 8. How it is built

PolicyForge is delivered by Claude Code agents under human supervision, with no hand-written production
code, using the Claude Harness Engine (planner → generator → evaluator loop, sprint contracts, quality
hooks) extended with insurance-specific agents, skills, commands and guard hooks. Requirements, specs and
reviews live in `specs/`; engineering records live in `docs/`.
