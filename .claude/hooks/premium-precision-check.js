#!/usr/bin/env node
'use strict';

// NFR-01 guard: premium, refund and sum-insured amounts are fixed-point (decimal.Decimal).
// Blocks any Write/Edit that introduces floating-point types into backend production code
// or migrations: float(...), ': float' / '-> float' annotations, float literals in
// arithmetic with money names, or SQLAlchemy Float columns.

const u = require('./lib/policyforge-hook-utils');

const SCOPES = [/^backend\/src\//, /^backend\/migrations\//];
// Money-ish identifiers as whole snake_case/camelCase parts (so `generate` does not match `rate`).
const MONEY = /(^|[^a-z])(premium|refund|sum_?insured|amount|rate|factor|loading|discount|fee|tax|gst|levy|price)s?(?![a-z])/i;

const RULES = [
  { re: /\bfloat\s*\(/, why: 'float(...) conversion' },
  { re: /(:|->)\s*(Optional\[)?float\b/, why: 'float type annotation' },
  { re: /\b(list|dict|tuple|set)\[[^\]]*\bfloat\b/, why: 'float inside a container type' },
  { re: /\b(sa\.|sqlalchemy\.)?Float\s*\(/, why: 'SQLAlchemy Float column (use Numeric(12, 2) + Decimal)' },
  { re: /\bmath\.(floor|ceil|fsum)\s*\(/, why: 'math float helper (use Decimal.quantize)' },
  { re: /\bround\s*\(/, why: 'round() (use Decimal.quantize(Decimal("0.01"), ROUND_HALF_UP))' },
];
const FLOAT_LITERAL = /(?<![\w."'])(\d+\.\d+([eE][-+]?\d+)?|\d+[eE][-+]?\d+)(?![\w."'])/;

const input = u.readInput();
if (!input) process.exit(0);
const filePath = (input.tool_input && input.tool_input.file_path) || '';
const rel = u.relativeToProject(filePath);
if (!rel.endsWith('.py') || !SCOPES.some((s) => s.test(rel))) process.exit(0);

const content = u.proposedContent(input);
if (content === null) process.exit(0);

const findings = [];
for (const { n, code } of u.codeLines(content)) {
  for (const rule of RULES) {
    if (rule.re.test(code)) findings.push(`line ${n}: ${rule.why} — ${code.trim()}`);
  }
  if (MONEY.test(code) && FLOAT_LITERAL.test(code) && !/Decimal\(\s*["']/.test(code)) {
    findings.push(`line ${n}: bare float literal in money expression — ${code.trim()}`);
  }
}

if (findings.length > 0) {
  u.block(
    'premium-precision-check (NFR-01)',
    rel,
    findings,
    'Use decimal.Decimal built from strings (Decimal("0.05")), Numeric columns, and quantize(Decimal("0.01"), ROUND_HALF_UP) at the final step. See .claude/skills/premium-calc-evaluator/SKILL.md.'
  );
}
process.exit(0);
