---
name: example-output-guard
description: >
  WHAT: keep long / whole-file code generation complete — no truncation, placeholders, "...",
  or "for brevity" stubs.
  USE WHEN: generating a whole file, a large template, or a big refactor (roughly >150 lines, or
  any "write the complete X" request); or when an earlier turn may have left a file half-written.
  DO NOT TRIGGER: a small edit (<~30 lines) to an existing file; a question; a prose-only answer.
tier: guard
oversight: high
---

# Output guard — finish what you generate

> **Announce on activation:** "Using example-output-guard — I'll generate the whole thing, no stubs."

A partial output is a broken output: a truncated function won't import, an empty template renders
blank, a query missing its filter returns everything. The cheapest place to catch that is before
you hit send.

## Banned in generated code

| Where | Don't emit |
|---|---|
| any language | `# ... rest of <thing>`, `# TODO: implement`, `# same as above`, a bare `pass` / `return None` left as a placeholder |
| templates | empty blocks (`{% block x %}{% endblock %}`), `{# ... #}` / `<!-- ... -->` standing in for real markup |
| SQL | `-- ... rest of query`, a CTE with no `SELECT`, conditions commented out |
| prose around code | "for brevity", "omitted for space", "etc.", "you can add the rest", "similar to above" |

## Too long for one turn? Continue, don't compress

Never shrink content to fit a reply. Instead:

1. Write completely **to a clean breakpoint** — end of a function, a closed template block, a finished CTE.
2. Mark where you stopped: `# === NEXT: <the next section> ===`.
3. Say what's left and how to resume: "Wrote through `<X>`. Say 'continue' for the rest."
4. Do **not** treat the file as done — or commit it — until every part is written.

## Before you send

- No banned pattern above is present.
- Every requested item is there and complete; code blocks hold runnable code, not a description of it.
- After writing a long file, re-read it and grep for the banned markers (`# ...`, `placeholder`,
  empty blocks) — any hit, fix it before moving on.

## Anti-rationalization

| You'll think | Reality |
|---|---|
| "I'll stub it and fill it in later" | "Later" ships as a `pass` that 500s on the first call. Write it now, or say plainly it isn't written. |
| "Truncating keeps the reply short" | A reply that doesn't run isn't short, it's wrong — the user pays a round-trip to ask again. |
| "They can obviously fill in the rest" | Then say so and stop at a clean breakpoint; don't bury a silent `...` mid-file. |

## Honest limit

This guards **completeness, not correctness**: it does **not** verify the code compiles or is
right — only that nothing is stubbed or truncated. The grep checks catch only literal banned
tokens; they cannot see a section you described but never wrote. It is a model-invoked skill
(bypassable), not a hook — see [`docs/guard-mechanisms.md`](../../../docs/guard-mechanisms.md).
