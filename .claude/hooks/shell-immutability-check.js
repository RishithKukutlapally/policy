#!/usr/bin/env node
'use strict';

// NFR-02 / NFR-05 guard for the Bash tool — closes the gap left by the Write/Edit hooks.
// Blocks shell commands that would mutate an append-only artefact:
//   - a committed Alembic migration (backend/migrations/versions/*.py)
//   - a committed PUBLISHED policy rule version (backend/policy_rules/<product>/v<N>.json)
//   - existing lines of backend/policy_rules/PUBLISHED.lock (appending with >> / tee -a is allowed)
//
// Best-effort by design: shell is Turing-complete, so this hook catches the common mutation forms
// (in-place editors, redirection, tee, dd, rm/mv/cp, git checkout/restore, inline interpreters,
// following `cd`). The authoritative backstop is CI: the architecture tests re-hash every PUBLISHED
// file against PUBLISHED.lock and diff migrations against the merge base (docs/decisions.md DEC-006).

const path = require('path');
const u = require('./lib/policyforge-hook-utils');

const MIGRATION = /^backend\/migrations\/versions\/[^/]+\.py$/i;
const RULE_FILE = /^backend\/policy_rules\/[a-z_]+\/v\d+\.json$/i;
const LEDGER = /^backend\/policy_rules\/published\.lock$/i;
const PROTECTED_DIRS = ['backend/migrations', 'backend/policy_rules', 'backend'];

const PATH_TOKEN = /[\w./\\-]*(migrations[\\/]versions[\\/][\w.-]+\.py|policy_rules[\\/][a-z_]+[\\/]v\d+\.json|PUBLISHED\.lock)/gi;
const IN_PLACE = /\b(sed|perl)\b[^|;&]*\s-{1,2}\w*i\b|\b(sed|perl)\b[^|;&]*--in-place|\btruncate\b|\bgit\s+(checkout|restore)\b|\b(python3?|node|ruby)\s+-(c|e)\b/;

function isProtected(rel, appendOnly) {
  if (LEDGER.test(rel)) return !appendOnly && u.committedContent('backend/policy_rules/PUBLISHED.lock') !== null;
  if (MIGRATION.test(rel)) return u.committedContent(rel) !== null;
  if (RULE_FILE.test(rel)) {
    const committed = u.committedContent(rel);
    return committed !== null && /"status"\s*:\s*"PUBLISHED"/i.test(committed);
  }
  return false;
}

// Remove quoted text so verbs inside strings (grep "rm" file) do not count; keep paths outside quotes.
function unquoted(segment) {
  return segment.replace(/(["'])(?:\\.|(?!\1).)*\1/g, ' ');
}

function splitSegments(command) {
  // `>|` (noclobber override) is a redirect, not a pipe — do not split on that `|`.
  return command.split(/;|&&|\|\||(?<!>)\||\n/).map((s) => s.trim()).filter(Boolean);
}

function redirectTargets(segment) {
  const out = [];
  const re = /(>>|>\||>)\s*("?)([^\s"&|;]+)\2|\bdd\b[^|;&]*\bof=("?)([^\s"&|;]+)\4/g;
  let m;
  while ((m = re.exec(segment)) !== null) {
    if (m[3]) out.push({ path: m[3], appendOnly: m[1] === '>>' });
    if (m[5]) out.push({ path: m[5], appendOnly: false });
  }
  return out;
}

function mutatedTargets(segment) {
  const bare = unquoted(segment);
  const targets = redirectTargets(segment);
  const tokens = segment.match(PATH_TOKEN) || [];
  const tee = bare.match(/(^|\s)tee\b(\s+-\w*a)?/);
  if (IN_PLACE.test(bare) || tee) {
    const appendOnly = Boolean(tee && tee[2]) && !IN_PLACE.test(bare);
    targets.push(...tokens.map((p) => ({ path: p, appendOnly })));
  }
  const verb = bare.match(/^\s*(cp|mv|rm|copy|move|del)\b(.*)$/i);
  if (verb) {
    const args = verb[2].trim().split(/\s+/).filter((a) => a && !a.startsWith('-'));
    const destIdx = /^(cp|copy)$/i.test(verb[1]) ? [args.length - 1] : args.map((_, i) => i);
    for (const i of destIdx) if (args[i]) targets.push({ path: args[i], appendOnly: false, dirOk: /^rm|^del/i.test(verb[1]) });
    if (/^cp$/i.test(verb[1]) && /\s-\w*t\s+(\S+)/.test(bare)) targets.push({ path: bare.match(/\s-\w*t\s+(\S+)/)[1], appendOnly: false });
  }
  return targets;
}

// rm -r backend/migrations (or a parent) removes committed migrations wholesale.
function removesProtectedDir(rel) {
  return PROTECTED_DIRS.includes(rel.replace(/\/+$/, '').toLowerCase());
}

const input = u.readInput();
if (!input || input.tool_name !== 'Bash') process.exit(0);
const command = (input.tool_input && input.tool_input.command) || '';

let cwd = input.cwd || process.env.CLAUDE_PROJECT_DIR || process.cwd();
const findings = [];
for (const segment of splitSegments(command)) {
  const cd = unquoted(segment).match(/^\s*(cd|pushd)\s+("?)([^\s"]+)\2\s*$/);
  if (cd) {
    cwd = path.resolve(cwd, cd[3]);
    continue;
  }
  for (const target of mutatedTargets(segment)) {
    const abs = path.resolve(cwd, target.path.replace(/^["']|["']$/g, ''));
    const rel = u.relativeToProject(abs);
    if (!rel) continue;
    if (isProtected(rel, target.appendOnly) || (target.dirOk && removesProtectedDir(rel))) {
      findings.push(`${rel} — mutated by: ${segment}`);
    }
  }
}

if (findings.length > 0) {
  u.block(
    'shell-immutability-check (NFR-02/05)',
    'Bash command',
    findings,
    'Committed migrations and PUBLISHED rule versions are append-only. Add a new Alembic revision or run /publish-policy-version <product> to create the next DRAFT version.'
  );
}
process.exit(0);
