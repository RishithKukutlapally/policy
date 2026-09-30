#!/usr/bin/env node
'use strict';

// NFR-03 guard: Aadhaar, PAN and health declarations are never written to logs.
// Blocks Write/Edit that put PII-bearing identifiers inside logging/print/console calls
// in backend or frontend code. Log a redacted token (e.g. customer_ref) instead, or pass
// the value through the redacting logger's `mask_pii` helper in backend/src/lib/.

const u = require('./lib/policyforge-hook-utils');

const SCOPES = [/^backend\/src\/.*\.py$/, /^backend\/migrations\/.*\.py$/, /^frontend\/src\/.*\.(ts|tsx)$/];
const LOG_CALL = /\b\w*(logger|logging|log|structlog)\.(debug|info|warning|warn|error|exception|critical|log|msg|bind)\s*\(|\bprint\s*\(|\bconsole\.(log|info|warn|error|debug|trace|table|dir)\s*\(/i;
// snake_case (backend) and camelCase (frontend) spellings of Aadhaar, PAN, health and KYC fields.
const PII = /\b(\w*aadh?aar\w*|pan|pan_?(no|num|number|card)\w*|\w*health_?decl\w*|\w*medical\w*|\w*pre_?existing\w*|\w*kyc_?doc\w*)\b/i;

// Replace string literals by their interpolated expressions only: f"{x}" / `${x}` keep x, "x" → "".
function stripStringText(text) {
  return text.replace(/([fF]?)(["'`])((?:\\.|(?!\2).)*)\2/g, (_, fPrefix, quote, body) => {
    const interp = quote === '`' ? /\$\{([^}]*)\}/g : fPrefix ? /\{([^}]*)\}/g : null;
    if (!interp) return '""';
    return ' ' + Array.from(body.matchAll(interp), (m) => m[1]).join(' ') + ' ';
  });
}

const input = u.readInput();
if (!input) process.exit(0);
const filePath = (input.tool_input && input.tool_input.file_path) || '';
const rel = u.relativeToProject(filePath);
if (!SCOPES.some((s) => s.test(rel))) process.exit(0);

const content = u.proposedContent(input);
if (content === null) process.exit(0);

// TS/TSX: only whole-line `//` comments are dropped — a `//` inside a string ("http://x") must not
// hide the rest of the line (clean-code review CC-037).
const lines = rel.endsWith('.py')
  ? u.codeLines(content)
  : content.split('\n').map((raw, i) => ({ n: i + 1, code: /^\s*\/\//.test(raw) ? '' : raw, raw }));

const findings = [];
for (let i = 0; i < lines.length; i++) {
  if (!LOG_CALL.test(lines[i].code)) continue;
  // A log call may span several lines — inspect up to the closing parenthesis (max 6 lines).
  let window = '';
  for (let j = i; j < Math.min(lines.length, i + 6); j++) {
    window += ' ' + lines[j].code;
    if (/\)\s*$/.test(lines[j].code.trim())) break;
  }
  // Each PII token must itself be wrapped: remove masked sub-expressions and plain string text
  // (labels like "aadhaar" are not data), keeping f-string / template-literal interpolations.
  const unmasked = stripStringText(window).replace(/\b(mask_pii|maskPii|redact\w*)\s*\([^()]*\)/gi, '');
  if (PII.test(unmasked)) {
    findings.push(`line ${lines[i].n}: PII identifier in log call — ${lines[i].code.trim()}`);
  }
}

if (findings.length > 0) {
  u.block(
    'pii-redaction-check (NFR-03)',
    rel,
    findings,
    'Never log Aadhaar, PAN or health declarations. Log an opaque reference (application_id, customer_ref) or wrap the value with mask_pii(...) from src.lib.'
  );
}
process.exit(0);
