# Plan Template

Copy this, fill it in, keep it to one screen. This file is only read when the
`awb-plan-then-code` skill reaches its planning step — an example of progressive
disclosure (the short `SKILL.md` stays cheap; this detail loads on demand).

```markdown
## Goal
One sentence: what will be true after this change that isn't true now.

## Files to change
- path/to/file_a — <what changes and why>
- path/to/file_b — <what changes and why>

## Approach
2-4 bullets on how.

## Out of scope (decided NOT to do)
- <thing you deliberately are NOT changing — this is what the review step grades the diff against>

## How I'll prove it worked (runnable checks)
- [ ] A check you can run and SHOW the output of (e.g. `pytest tests/test_x.py` and its PASS line), not "works correctly"
- [ ] Observable check 2

## Risks / unknowns
- <thing that might bite> -> <how you'll de-risk it>
```

## Tips

- If "Files to change" has more than ~6 entries, consider splitting into phases.
- Every acceptance item must be **observable** — "works correctly" is not observable;
  "`pytest tests/test_x.py` passes" is.
- The "Out of scope" section is your defense against silent scope creep — it is what the
  review step grades the diff against.
