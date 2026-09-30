#!/usr/bin/env node
'use strict';

// NFR-02 guard: policy versions, endorsements, state transitions, refunds, underwriting
// overrides and audit records are append-only — no UPDATE or DELETE, ever.
// Blocks Write/Edit in backend repository/service code (and migrations) that issues
// update/delete against those entities via SQLAlchemy or raw SQL.

const u = require('./lib/policyforge-hook-utils');

const SCOPES = [/^backend\/src\/(repository|service)\/.*\.py$/, /^backend\/migrations\/versions\/.*\.py$/];

// Canonical append-only entities — keep in sync with docs/conventions.md "Persistence".
const MODELS = [
  'RuleSetVersion', 'UnderwritingDecision', 'UnderwritingOverride', 'PolicyStateTransition',
  'Endorsement', 'PremiumPayment', 'Refund', 'AuditRecord',
];
const TABLES = [
  'rule_set_versions', 'underwriting_decisions', 'underwriting_overrides', 'policy_state_transitions',
  'endorsements', 'premium_payments', 'refunds', 'audit_records',
];
const SNAKE = [
  'rule_set_version', 'rule_version', 'decision', 'override', 'transition',
  'endorsement', 'payment', 'refund', 'audit',
];

const modelAlt = MODELS.join('|');
const RULES = [
  { re: new RegExp(`\\b(update|delete)\\(\\s*(${modelAlt})\\b`), why: 'SQLAlchemy update()/delete() on append-only model' },
  // Case-sensitive on purpose: SQL keywords are upper-case by convention, so prose such as
  // "cannot update endorsements" in an error message does not trip the rule.
  { re: new RegExp(`\\b(UPDATE|DELETE\\s+FROM)\\s+["\`]?(${TABLES.join('|')})\\b`), why: 'raw SQL UPDATE/DELETE on append-only table' },
  { re: new RegExp(`\\bop\\.(drop_table|drop_column|alter_column)\\(\\s*["'](${TABLES.join('|')})["']`), why: 'migration drops/alters append-only table' },
];
const SESSION_DELETE = /\.(delete|merge)\(\s*([a-z_][\w.]*)\s*\)/;
const QUERY_MUTATE = /\.query\(\s*(\w+)\s*\)[\s\S]*\.(update|delete)\(/;

const input = u.readInput();
if (!input) process.exit(0);
const filePath = (input.tool_input && input.tool_input.file_path) || '';
const rel = u.relativeToProject(filePath);
if (!SCOPES.some((s) => s.test(rel))) process.exit(0);

const content = u.proposedContent(input);
if (content === null) process.exit(0);

const findings = [];
for (const { n, code } of u.codeLines(content)) {
  for (const rule of RULES) {
    if (rule.re.test(code)) findings.push(`line ${n}: ${rule.why} — ${code.trim()}`);
  }
  const del = code.match(SESSION_DELETE);
  if (del && SNAKE.some((s) => del[2].toLowerCase().includes(s))) {
    findings.push(`line ${n}: session.${del[1]}() on append-only record '${del[2]}' — ${code.trim()}`);
  }
  const q = code.match(QUERY_MUTATE);
  if (q && MODELS.includes(q[1])) {
    findings.push(`line ${n}: query(${q[1]}).${q[2]}() on append-only model — ${code.trim()}`);
  }
}

if (findings.length > 0) {
  u.block(
    'append-only-repository-check (NFR-02)',
    rel,
    findings,
    'Append a new row instead (RuleSetVersion, UnderwritingDecision, UnderwritingOverride, PolicyStateTransition, Endorsement, PremiumPayment, Refund, AuditRecord — docs/conventions.md). Current state is the projection row or the latest appended row.'
  );
}
process.exit(0);
