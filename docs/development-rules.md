# Development rules — defaults for everyday code

These are the day-to-day defaults the agent codes by when nothing more specific applies. They are
**guidance, not law**: each one earns its place by changing what you *do*, and each yields to a
documented, narrower rule when the two disagree (see [When rules conflict](#when-rules-conflict)).
The stance behind "guidance, not gospel" is one of the four tenets — see
[`PHILOSOPHY.md`](../PHILOSOPHY.md); this page is the operational list, not the rationale.

## Foundational principles

Three old principles, kept because each names a *failure mode* — and each has a counter-failure that
makes it a judgement call, not a reflex:

- **YAGNI** — build for the requirement in front of you, not a hypothetical future one. The cost of
  the abstraction you didn't need is paid today; the flexibility you imagined is usually never used.
- **KISS** — prefer the plain version a stranger can read over the clever one that saves a few lines.
  Cleverness is a loan against the next person to touch the code (often you, months later).
- **DRY** — factor out a duplication once it is *real and stable* (the rule of thumb is three live
  copies that change together). Extracting after one or two sightings couples things that only
  *looked* alike and is harder to unpick than the duplication would have been.

The through-line: each principle has an opposite failure (over-abstraction, premature DRY,
under-engineering). The skill is knowing which failure you're closer to *right now*.

## Size is a signal, not a limit

A long file or function is a prompt to *look*, not an automatic defect. Some stay large on purpose —
a linear pipeline with a clear section index reads worse when fragmented across files. Treat
thresholds (a function past ~80 lines, a file past a few hundred) as "stop and ask whether this has
a natural seam," not as a gate that fails the build. Split when there is a real seam; leave it when
splitting would only scatter one coherent flow.

## Code-quality defaults

Prioritise, in order:

- **Correctness over style** — a passing, honest test is the precondition; formatting is downstream.
- **Readability over brevity** — optimise for the reader, not the character count.
- **Type hints and a one-line docstring on the public surface** — the signature and the return
  contract are the cheapest documentation there is.

Avoid, by default:

- **Dead code** — delete it; don't leave commented-out blocks. Version control is the archive.
- **Wildcard and unused imports** — they hide what a module actually depends on.
- **Mutable default arguments** (`def f(x=[])`) — the classic shared-state trap.
- **Unexplained magic numbers** — name the constant or read it from config.

## Error handling

- **Validate at the boundary, trust inward.** Check untrusted input where it enters the system (a
  request handler, an external API response); don't re-validate the same value at every internal
  layer — that duplicates the check and lies about where trust begins.
- **Raise specific, catch narrow.** Raise the precise exception (`FileNotFoundError`, `ValueError`,
  a small custom error) and catch only what you can actually handle. A bare `except Exception` that
  keeps going turns a loud failure into a silent wrong answer.
- **Release resources with `try/finally`** (or a context manager) so a failure mid-operation still
  closes the file or connection.
- **Swallow an exception only when failing open is the intended behaviour** — and say so in a
  comment. The repo's hooks do exactly this on purpose (a guardrail must never crash the agent), and
  the [`silent-failure-hunter`](../.claude/agents/silent-failure-hunter.md) agent exists to catch the
  cases where it *wasn't* intentional.

## Testing

- **New behaviour ships with a test.** Code without one is a claim you haven't checked.
- **A regression test fails before the fix and passes after.** If it's green before you change
  anything, it isn't testing the bug.
- **Prefer integration over deep mocking.** A test wired through three layers of mocks mostly tests
  the mocks. Reach for a real (in-memory) dependency when you can.
- **Use a golden master for gnarly logic** — pin the known-good output and diff against it, rather
  than asserting a dozen fields by hand.

## Commits

Commit message conventions are canonical in [`CLAUDE.md`](../CLAUDE.md) ("Commit conventions") — type
prefix, imperative mood, *why* in the body, no AI co-author trailers. This page does not restate
them; follow that section.

## When rules conflict

A general rule here is a default; a **path-scoped rule** in [`.claude/rules/`](../.claude/rules/)
written for a specific kind of file is more informed, so the specific one wins. The requirement is
that the exception be *written down* — an undocumented deviation is indistinguishable from a mistake.
Capturing a recurring exception as a rule is its own discipline; see
[`lessons-as-rules.md`](lessons-as-rules.md).

## Honest limit

This is a convention, not an enforcer. Nothing in the repo checks that you applied YAGNI or validated
at the boundary; the linters and the [leak/command guards](../.claude/hooks/) catch a few mechanical
slips, but most of this list is judgement that no gate can make for you. It sets the default so the
agent re-derives the same choices each session — it can't substitute for thinking about the case in
front of you.
