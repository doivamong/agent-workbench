# Plan Template

Copy this, fill it in, keep it to one screen. This file is only read when the
`example-plan-then-code` skill reaches its planning step — an example of progressive
disclosure (the short `SKILL.md` stays cheap; this detail loads on demand).

```markdown
## Goal
One sentence: what will be true after this change that isn't true now.

## Files to change
- path/to/file_a — <what changes and why>
- path/to/file_b — <what changes and why>

## Approach
2-4 bullets on how. Note anything you deliberately decided NOT to do (scope guard).

## How I'll know it worked (acceptance)
- [ ] Observable check 1 (a test name, a command output, a UI state)
- [ ] Observable check 2

## Risks / unknowns
- <thing that might bite> -> <how you'll de-risk it>
```

## Tips

- If "Files to change" has more than ~6 entries, consider splitting into phases.
- Every acceptance item must be **observable** — "works correctly" is not observable;
  "`pytest tests/test_x.py` passes" is.
- The "decided NOT to do" line is your defense against silent scope creep.
