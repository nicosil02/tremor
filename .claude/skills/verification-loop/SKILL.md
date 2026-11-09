---
name: verification-loop
description: Run a six-phase verification of a Claude Code session's work — build, type check, lint, tests, security grep, and diff review — then produce a PASS/FAIL verification report. Use when verifying work after completing a feature or refactor, before creating a PR, or when quality gates must pass.
license: MIT
metadata:
  origin: ECC
---

# Verification Loop Skill

A comprehensive verification system for Claude Code sessions.

## When to Use

Invoke this skill:
- After completing a feature or significant code change
- Before creating a PR
- When you want to ensure quality gates pass
- After refactoring

## Verification Phases

In Tremor (Python + SQLite, Windows locally, GitHub Actions in CI) the phases are below. Commands work in Git Bash
and in the Actions runner. No npm, no paid scanners. A phase whose tool is not installed is reported as SKIPPED,
not PASS.

### Phase 1: Build Verification
```bash
# Every module compiles (catches syntax errors in files no test imports)
python -m compileall -q tremor tests streamlit_app.py
```

If build fails, STOP and fix before continuing.

### Phase 2: Type Check
Tremor has no type checker in `requirements.txt`. Mark SKIPPED unless `pyright` or `mypy` is already installed;
do not install one just for this.

### Phase 3: Lint Check
```bash
# Only if ruff is already installed; otherwise SKIPPED
ruff check tremor tests 2>&1 | sed -n '1,30p'
```

### Phase 4: Test Suite
```bash
python -m pytest -q 2>&1 | tail -20
```

Report total, passed and failed. Tremor has no coverage target: the rule is one small test per non-trivial
logic (CLAUDE.md), so check that new logic in the diff has its test instead of measuring a percentage.

### Phase 5: Security Scan
```bash
# Keys: Groq (gsk_), Google/Gemini (AIza), generic api_key assignments, in tracked files and history
git grep -nE "gsk_[A-Za-z0-9]{10,}|AIza[0-9A-Za-z_-]{20,}" | head -10
git log -p | grep -nE "gsk_[A-Za-z0-9]{10,}|AIza[0-9A-Za-z_-]{20,}" | head -5
git grep -nE "(api_key|API_KEY)\s*=\s*['\"][^'\"]+" -- '*.py' | head -10

# Data that must not reach main: the database, datos/, Credenciales.docx
git diff --cached --name-only | grep -E "^datos/|\.db$|Credenciales" || echo "staged files OK"
```

Also check the privacy rules from CLAUDE.md in the diff: actors named by role (no person names), no `Comentar_t`
from the EGPP, and `acled_evento` never in anything published to `datos`.

### Phase 6: Diff Review
```bash
# Show what changed
git diff --stat
git diff HEAD~1 --name-only
```

Review each changed file for:
- Unintended changes
- Missing error handling
- Potential edge cases

## Target Acceptance

When the requested outcome requires deployment or target-environment verification,
report target acceptance separately from local checks. Record the environment and
installed version when known, the evidence, and the next permitted check or precise
access dependency. Passing local checks, review, merge, or release does not establish
target acceptance. Report VERIFIED or FAILED for an executed target check, with its evidence.
Do not access production or make external changes without authorization. For
local-only tasks, mark target acceptance as not applicable.
In Tremor the targets are the `datos` branch, the published page and the workflows on `main`: pushing to
`datos`, publishing or commenting on issues needs the author's go-ahead first (CLAUDE.md).

For example: local checks PASS; staging verification NOT PERFORMED (no access);
next step: an authorized maintainer runs the staging smoke test.

## Output Format

After running all phases, produce a verification report:

```
VERIFICATION REPORT
==================

Build:     [PASS/FAIL]
Types:     [PASS/FAIL] (X errors)
Lint:      [PASS/FAIL] (X warnings)
Tests:     [PASS/FAIL] (X/Y passed)
Security:  [PASS/FAIL] (X issues)
Diff:      [X files changed]

Overall:   [READY/NOT READY] for PR
Target:    [VERIFIED/FAILED/NOT PERFORMED/NOT APPLICABLE] (environment/version, evidence)
Next permitted step: [check or access dependency; none if complete/not applicable]

Issues to Fix:
1. ...
2. ...
```

## Continuous Mode

For long sessions, run verification every 15 minutes or after major changes:

```markdown
Set a mental checkpoint:
- After completing each function
- After finishing a component
- Before moving to next task

Run this skill again (there is no /verify command in Tremor).
```

## Hooks

Tremor installs no hooks for this. Run the phases by hand, before every PR.
