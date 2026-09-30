#!/usr/bin/env node
'use strict';

// Self-test for the PolicyForge guard hooks. Run: node .claude/hooks/tests/run-hook-tests.js
// Builds a throwaway git repo (used as CLAUDE_PROJECT_DIR) with a committed migration, a PUBLISHED
// and a DRAFT rule file and a PUBLISHED.lock ledger, then pipes synthetic tool calls into each hook
// and asserts block (exit 2) / allow (exit 0). Regression ids refer to specs/reviews/*-substrate.md.

const { spawnSync, execSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const HOOKS = path.resolve(__dirname, '..');
const repo = fs.mkdtempSync(path.join(os.tmpdir(), 'pf-hooks-'));
const put = (rel, s) => {
  fs.mkdirSync(path.dirname(path.join(repo, rel)), { recursive: true });
  fs.writeFileSync(path.join(repo, rel), s);
};
fs.mkdirSync(path.join(repo, '.claude'));
put('backend/migrations/versions/0001_init.py', 'x = 1\n');
put('backend/migrations/versions/0002_Add_Refunds.py', 'x = 1\n');
put('backend/policy_rules/motor/v1.json', '{"status":"PUBLISHED"}');
put('backend/policy_rules/motor/v2.json', '{"status":"DRAFT"}');
put('backend/policy_rules/PUBLISHED.lock', 'abc123  backend/policy_rules/motor/v1.json\n');
const git = '-c user.email=hooks@test -c user.name=hooks -c core.autocrlf=false';
execSync(`git init -q && git ${git} add -A && git ${git} commit -qm init`, { cwd: repo });

const env = { ...process.env, CLAUDE_PROJECT_DIR: repo };
const write = (rel, content) => ({ tool_name: 'Write', cwd: repo, tool_input: { file_path: path.join(repo, rel), content } });
const bash = (command) => ({ tool_name: 'Bash', cwd: repo, tool_input: { command } });
const BLOCK = 2;
const ALLOW = 0;

const P = 'premium-precision-check.js';
const I = 'policy-immutability-check.js';
const X = 'pii-redaction-check.js';
const A = 'append-only-repository-check.js';
const S = 'shell-immutability-check.js';

const cases = [
  // NFR-01 money precision
  [P, write('backend/src/domain/premium.py', 'def premium(x: float) -> float:\n    return x * 1.05\n'), BLOCK],
  [P, write('backend/src/domain/premium.py', 'def premium(x: Decimal) -> Decimal:\n    return (x * Decimal("1.05")).quantize(Decimal("0.01"), ROUND_HALF_UP)\n'), ALLOW],
  [P, write('backend/src/repository/models.py', 'premium = mapped_column(sa.Float())\n'), BLOCK],
  [P, write('backend/tests/unit/test_x.py', 'x: float = 1.5\n'), ALLOW],
  [P, write('Backend/SRC/domain/p.py', 'def f(x: float): ...\n'), BLOCK, 'M2 case-insensitive path'],
  [P, write('backend/src/domain/p.py', 'y = float(x)\n'), BLOCK, 'M1 cwd outside project', os.tmpdir()],
  [P, write('backend/src/domain/p.py', 's = "#"; premium = float(x)\n'), BLOCK, 'L3 # inside string'],
  [P, write('backend/src/domain/p.py', 'premium = Decimal("1.05")  # float is banned\n'), ALLOW],
  [P, write('backend/src/service/x.py', 'def generate(timeout=2.5):\n    pass\n'), ALLOW, 'CC-013 generate != rate'],
  [P, write('backend/src/domain/tax.py', 'GST = 0.18\n'), BLOCK, 'CC-013 gst'],
  // NFR-03 PII in logs
  [X, write('backend/src/service/app.py', 'logger.info("kyc ok", extra={"aadhaar": app.aadhaar_number})\n'), BLOCK],
  [X, write('backend/src/service/app.py', 'logger.info(\n    "kyc",\n    pan_number=pan,\n)\n'), BLOCK],
  [X, write('backend/src/service/app.py', 'logger.info("kyc ok", extra={"aadhaar": mask_pii(a)})\n'), ALLOW],
  [X, write('backend/src/service/app.py', 'logger.info("application submitted", extra={"application_id": aid})\n'), ALLOW],
  [X, write('backend/src/service/app.py', 'logger.info(f"kyc for {aadhaar_number}")\n'), BLOCK, 'f-string interpolation'],
  [X, write('backend/src/service/k.py', 'logger.info("kyc", a=mask_pii(aadhaar), p=pan_number)\n'), BLOCK, 'CC-033'],
  [X, write('frontend/src/pages/Apply.tsx', 'console.log(form.panNumber, form.pan)\n'), BLOCK],
  [X, write('frontend/src/pages/Apply.tsx', 'console.log(form.healthDeclaration)\n'), BLOCK, 'L4 camelCase'],
  [X, write('frontend/src/pages/Apply.tsx', 'console.log(`saved ${form.aadhaarNumber}`)\n'), BLOCK, 'template literal'],
  [X, write('frontend/src/pages/Apply.tsx', 'console.log("saved", policyNumber)\n'), ALLOW],
  // NFR-02 append-only repositories
  [A, write('backend/src/repository/endorsement_repository.py', 'self._session.delete(endorsement)\n'), BLOCK],
  [A, write('backend/src/repository/endorsement_repository.py', 'stmt = update(Endorsement).values(x=1)\n'), BLOCK],
  [A, write('backend/src/repository/policy_repository.py', 'stmt = update(Policy).values(status=s)\nself._session.add(endorsement)\n'), ALLOW],
  [A, write('backend/src/repository/r.py', 'conn.execute(text("DELETE FROM refunds WHERE id=1"))\n'), BLOCK],
  [A, write('backend/src/service/s.py', 'payload.update(extra)\n'), ALLOW],
  [A, write('backend/src/service/e.py', 'raise ValueError("cannot update endorsements")\n'), ALLOW, 'CC-013 prose'],
  [A, write('backend/src/repository/d.py', 'stmt = update(UnderwritingDecision)\n'), BLOCK, 'CC-002'],
  [A, write('backend/src/repository/p.py', 'self._session.delete(premium_payment)\n'), BLOCK, 'CC-002'],
  // NFR-02/05 immutability via Write/Edit
  [I, write('backend/migrations/versions/0001_init.py', 'x = 2\n'), BLOCK],
  [I, write('backend/migrations/versions/0002_next.py', 'x = 2\n'), ALLOW],
  [I, write('backend/policy_rules/motor/v1.json', '{"status":"PUBLISHED","x":1}'), BLOCK],
  [I, write('backend/policy_rules/MOTOR/v1.json', '{"status":"PUBLISHED","x":2}'), BLOCK, 'CC-001 casing'],
  [I, write('backend/policy_rules/motor/v2.json', '{"status":"DRAFT","x":1}'), ALLOW],
  [I, write('backend/policy_rules/PUBLISHED.lock', 'abc123  backend/policy_rules/motor/v1.json\ndef456  backend/policy_rules/motor/v2.json\n'), ALLOW, 'CC-016 append'],
  [I, write('backend/policy_rules/PUBLISHED.lock', 'def456  backend/policy_rules/motor/v2.json\n'), BLOCK, 'CC-016 rewrite'],
  // NFR-02/05 immutability via Bash (M4 / CC-015)
  [S, bash("sed -i 's/1/2/' backend/migrations/versions/0001_init.py"), BLOCK],
  [S, bash('echo {} > backend/policy_rules/motor/v1.json'), BLOCK],
  [S, bash('rm backend/migrations/versions/0001_init.py'), BLOCK],
  [S, bash('cp backend/policy_rules/motor/v2.json backend/policy_rules/motor/v1.json'), BLOCK],
  [S, bash('cp backend/policy_rules/motor/v1.json backend/policy_rules/motor/v3.json'), ALLOW],
  [S, bash('cat backend/migrations/versions/0001_init.py && uv run alembic upgrade head'), ALLOW],
  [S, bash("sed -i 's/a/b/' backend/policy_rules/motor/v2.json"), ALLOW],
  [S, bash('echo "def456  backend/policy_rules/motor/v2.json" >> backend/policy_rules/PUBLISHED.lock'), ALLOW],
  [S, bash('echo x > backend/policy_rules/PUBLISHED.lock'), BLOCK],
  [S, bash("sed -i '1d' backend/policy_rules/PUBLISHED.lock"), BLOCK],
  // Round-2 regressions (specs/reviews/clean-code-review-substrate.md, security-review-substrate.md)
  [S, bash("cd backend && sed -i 's/1/2/' migrations/versions/0001_init.py"), BLOCK, 'CC-035 follows cd'],
  [S, bash('cd backend/policy_rules && echo {} > motor/v1.json'), BLOCK, 'CC-035 follows cd'],
  [S, bash("sed -e 's/1/2/' -i backend/migrations/versions/0001_init.py"), BLOCK, 'M4 sed -e .. -i'],
  [S, bash("perl -p -i -e 's/1/2/' backend/migrations/versions/0001_init.py"), BLOCK, 'M4 perl -p -i'],
  [S, bash('echo x >| backend/migrations/versions/0001_init.py'), BLOCK, 'M4 >|'],
  [S, bash('dd if=/dev/zero of=backend/migrations/versions/0001_init.py count=1'), BLOCK, 'M4 dd of='],
  [S, bash("python -c \"open('backend/migrations/versions/0001_init.py','w')\""), BLOCK, 'M4 inline interpreter'],
  [S, bash('rm -rf backend/migrations'), BLOCK, 'M4 rm -r parent dir'],
  [S, bash('grep "rm" backend/migrations/versions/0001_init.py'), ALLOW, 'R2-L3 verb inside quotes'],
  [I, write('backend/migrations/versions/0002_add_refunds.py', 'x = 2\n'), BLOCK, 'CC-036 case lookup'],
  [X, write('frontend/src/pages/Apply.tsx', 'console.log("http://x", form.pan)\n'), BLOCK, 'CC-037 // in string'],
  [X, write('frontend/src/pages/Apply.tsx', '// console.log(form.pan)\n'), ALLOW, 'whole-line comment'],
  [P, write('backend/src/domain/rates.py', 'premium_rate = 1e-2\n'), BLOCK, 'scientific float literal'],
];

let failed = 0;
for (const [hook, payload, expected, note, cwd] of cases) {
  const r = spawnSync('node', [path.join(HOOKS, hook)], {
    input: JSON.stringify(payload), encoding: 'utf8', env, cwd: cwd || repo,
  });
  const ok = r.status === expected;
  if (!ok) failed++;
  const target = payload.tool_input.command || path.relative(repo, payload.tool_input.file_path);
  console.log(`${ok ? 'PASS' : 'FAIL'} ${hook.padEnd(33)} ${expected === BLOCK ? 'block' : 'allow'} ${target}${note ? `  [${note}]` : ''}`);
  if (!ok && r.stderr) console.log(r.stderr.trim().replace(/^/gm, '     '));
}
fs.rmSync(repo, { recursive: true, force: true });
console.log(`\n${cases.length - failed}/${cases.length} passed`);
process.exit(failed ? 1 : 0);
