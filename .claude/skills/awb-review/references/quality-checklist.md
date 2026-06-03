# Stage 2 Quality Checklist

Loaded only when `awb-review` reaches Stage 2. Tune this to your language and project;
the point is that it lives *outside* `SKILL.md` so the skill stays scannable.

## Correctness
- [ ] Handles the empty / null / zero case.
- [ ] Error paths do something sensible (not a bare `except: pass`).
- [ ] External resources (files, connections, locks) are released on every path.
- [ ] No off-by-one / boundary mistakes in loops and slices.

## Clarity
- [ ] Names say what the thing is/does; no single-letter mystery vars in non-trivial scope.
- [ ] No commented-out code or dead branches left behind.
- [ ] Comments explain *why*, not *what* (the code already shows what).

## Tests
- [ ] New behaviour has a test that would fail without the change.
- [ ] A regression being fixed has a test that reproduces it first.

## Consistency
- [ ] Matches the style and patterns of the surrounding code.
- [ ] No new dependency added for something the stdlib / existing deps already do.

## Security & data (when relevant)
- [ ] User input is validated at the boundary.
- [ ] No secret, key, or token hardcoded or logged.
- [ ] Output that crosses a trust boundary is escaped/encoded.
