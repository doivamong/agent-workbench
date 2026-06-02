# Trusting an external analysis tool — benchmark before you believe it

You adopt a tool that answers questions about your codebase — a call-graph server, a dependency
mapper, a "find all callers" index, an LLM-backed code search. It returns confident answers. The trap
is that **a confident answer is not a correct one**, and a tool that is wrong *silently* is worse than
no tool: it doesn't error, it just hands you a clean number that happens to be false, and you build on
it. This is the same failure the [`measurement-honesty`](../.claude/rules/measurement-honesty.md) rule
names as *coverage blindness* (a green checker that scanned the wrong thing), applied to a whole tool
instead of one check. The standard is [`PHILOSOPHY.md`](../PHILOSOPHY.md): honest about limits.

## The protocol

**1. Benchmark accuracy against ground truth — before you rely on it.**
Pick a primitive you already trust (`grep`/`rg`, the language's own tooling, manual reads) as ground
truth. Run a representative set of the tool's queries and compare. You are not testing whether the
tool *runs*; you are testing whether each *answer class* is right on *your* code.

**2. Ban the query classes that measure 0% (or wildly off).**
Accuracy is rarely uniform — a tool can be perfect at one question and useless at another. Write down,
per query type, "reliable / noisy / unusable," and **refuse to use the unusable ones** even though
they exist and return plausible output. The most dangerous query is the one that confidently returns
`0` when the truth is `159`.

**3. Keep — and prefer — the classes that measure reliable.**
The same tool's *structural* queries (what's in this file, which functions are over N lines, find a
symbol by name) are often 100% accurate while its *relationship* queries (who calls this, what's the
blast radius, which tests cover this) are broken. Use it for what it's good at; don't throw the whole
tool away for one bad class.

**4. Check staleness before every use.**
A derived index reflects the code *as of its last build*. Check freshness first; rebuild if stale;
build if absent. A correct answer about old code is still a wrong answer.

**5. Degrade gracefully to the primitive you trust.**
When the tool is unavailable (server down, timeout, locked DB), **do not block** and **do not retry in
a loop** — try once, then fall back to the ground-truth primitive and say so ("graph unavailable,
using grep fallback"). The fallback is always available; the tool is a speedup, not a dependency.

## Worked example — a code-graph server

A call-graph tool benchmarked against `grep` on a real codebase split cleanly in two:

| Query class | Tool answer | Ground truth (grep) | Verdict |
|---|---|---|---|
| "who calls this function?" | `0 callers` | dozens to hundreds of calls | **unusable (0%)** |
| "who imports this module?" | `0 importers` | many files | **unusable (0%)** |
| "what tests cover this?" | `0 tests` | test files exist | **unusable (0%)** |
| "blast radius, depth 1 / 2" | `0` / inflated ~4× | the real set | **unusable / noisy** |
| "what's in this file?" | exact | exact | **reliable (100%)** |
| "functions over N lines" | exact | exact | **reliable** |

**Root cause:** the codebase used function-local ("lazy") imports almost everywhere, and the graph
builder resolved call targets only against *top-level* imports — so the call edges for lazily-imported
functions were never created. The parser *could* see the imports; the graph *logic* dropped them. The
lesson is not "that tool is bad" — it's that **you cannot know which class is broken until you measure,
and the breakage is invisible from the output alone.**

The response was exactly the protocol: ban the relationship queries, keep the structural ones, and
fall back to documented `grep` patterns for callers / importers / tests / blast-radius. The kit's own
[`tools/affected_tests.py`](../tools/affected_tests.py) exists partly because of this — a
test-selection answer you can re-derive from `ast` beats one from an index you can't verify.

## Why this isn't just "tools have bugs"

The point is the **default stance toward a confident external answer**: treat it as a *claim to be
verified on your data*, not a fact, until you've benchmarked the class it belongs to. The cost of the
benchmark is an afternoon; the cost of trusting a silent `0` is a refactor that deletes "unused" code
that 159 callers depend on.

---

## Honest limits

- **This is a discipline, not a checker.** Nothing here measures the tool for you. It sets the default
  question — "did I benchmark this answer class, or am I trusting it?" — so you catch the silent-wrong
  case yourself.
- **Benchmarks are samples.** "Reliable on the cases I tried" is not "reliable always" — re-check when
  the codebase shape changes (a new import style, a new language, a big refactor) since that's exactly
  what breaks a derived index. Apply the same n=1 caution the
  [`measurement-honesty`](../.claude/rules/measurement-honesty.md) rule does.
- **The example is illustrative.** Specific accuracy figures came from one codebase and one tool
  version; yours will differ. The transferable part is the *method* (benchmark → triage by class →
  ban the bad → degrade to a trusted primitive), not the numbers.
