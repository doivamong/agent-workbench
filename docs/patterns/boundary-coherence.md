# Boundary coherence — read both sides of a contract

Two pieces of code that meet at a boundary share an **implicit contract**: a producer makes
something in a shape, a consumer reads it expecting that shape. The trap is that each side can be
edited in isolation and look correct on its own — while the contract between them quietly drifts.
Worse, the break is usually **silent**: no exception, just a blank section, a `None` that travels,
a handler that never fires. And a test that exercises one side still passes. (This is the general
parent of the [config-access](config-access.md) silent-`None` trap, and the producer/consumer face
of the [measurement-honesty](../../.claude/rules/measurement-honesty.md) "one-sided green check".)

## The rule

**When you change one side of a producer↔consumer boundary, open the other side and diff the
contract.** Don't trust "my side is correct" — correctness is a property of the *pair*, not either
half.

## Where boundaries hide (and how they fail silently)

| Producer | Consumer | A drift that fails *silently* |
|---|---|---|
| a view passes context variables | a template reads `{{ items }}` | rename the variable → the page renders **blank**, no error |
| a function returns a dict / record shape | a caller reads `result["total"]` | producer renames the key → `KeyError`, or a silent `None` that detonates downstream |
| a migration defines a column | a query `SELECT`s that column | column renamed / retyped → the query fails late, or reads the wrong field |
| an event / message carries a payload | a handler reads a field off it | emitter changes the shape → the handler reads a missing field and quietly no-ops |
| a server returns a fragment with an id | client code targets that id | the id the client expects isn't in the response → the update **never happens**, silently |

The thread: a one-sided edit can leave each half internally valid and the *joint* broken — with no
exception to point at the cause.

## The habit

- **Touch one side → read the other in the same change.** Open both; line up every name the consumer
  reads against what the producer actually emits.
- **When you rename or reshape the producer, find every consumer** (grep the field/name across the
  codebase) and update them together — a reshape is never a one-file edit.
- **Verify a whole slice end to end** right after you write it, not in a QA pass at the end. One
  slice = one complete boundary (producer + consumer exercised through the real path).

## Self-check (before committing a change that touches a boundary)

- Changed a producer's output shape → did you grep and update every consumer of it?
- Edited a template / view → do all the names it reads exist in what the view passes?
- Queried a column / field → did you confirm it against the real schema, not the spec you remember?
- Wired a target / handler to a producer → does the thing it points at actually exist in the response?

## Honest limit

This is a habit, not a checker — nothing here verifies that the two sides agree. Where a boundary is
load-bearing and stable, encode the contract so a machine checks it: a schema/contract test, a
greppable [invariant](../../tools/invariants.py), or a [path-scoped rule](../lessons-as-rules.md)
that fires when either side is edited. "Read both sides" is the cheap default underneath that, for
the many boundaries that never earn a formal contract test.
