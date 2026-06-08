---
name: prompt-refiner
description: >
  WHAT: turn a vague, multi-part request into a crisp, executable one before doing
  any work — clarify intent, surface hidden assumptions, restate the scope.
  USE WHEN: a request is long but underspecified (no files, no acceptance criteria,
  several intents at once). The UserPromptSubmit hook (prompt-refiner-inject.py) flags
  these automatically and asks you to run this first.
  DO NOT TRIGGER: the request is already specific (file paths, clear outcome); it's a
  trivial one-liner; or the user prefixed it to bypass refinement.
tier: workflow
---

# Prompt refiner

> **Announce on activation:** "Using prompt-refiner — I'll confirm scope before executing."

The cheapest place to fix a misunderstanding is *before* the work starts. This skill is a
30-second gate, not a ceremony.

## Process

1. **Classify intent.** Is this a fix, a feature, a review, research, or a question? If two or
   more at once, that's a sign the request needs splitting.
2. **Spot the ambiguity — and don't trust the premises.** What's missing that changes what you'd
   build — scope, target files, expected output, constraints, the definition of done? If the
   request asserts "X already does Y" or names a file, grep/read to **verify the claim** first — a
   confident wrong premise is the most expensive ambiguity. Scan the requirement-level dimensions
   too — data shape, terminology consistency, and whether the acceptance check is actually
   testable — and when several are unclear, surface the highest **impact × uncertainty** one first.
3. **Decide the path by clarity (a 4-tier scale):**
   - *Crystal* → restate it in one line and proceed (no friction).
   - *One missing piece* → ask exactly one focused question, then proceed.
   - *Several intents / wide-open scope* → propose a concrete interpretation (scope + acceptance
     criteria) and get a yes before building.
   - *Claims-heavy or high-stakes* → **grill mode**: interview one focused question at a time,
     verifying each load-bearing claim against the code, until the spec is airtight.
4. **Restate, don't expand.** The rewrite must preserve the original intent — never quietly add
   scope the user didn't ask for. Shorter and sharper, not longer. An ambiguity you choose to
   proceed *past* becomes a **stated assumption**, never a silent default — surface it on the
   `Assumptions` line so a wrong guess is visible and correctable, not discovered after the build.

## Output shape

```
Intent: <fix | feature | review | research | question>
Restated: <one sentence, the crisp version>
Acceptance: <observable check(s) that mean "done">
Open question (if any): <the single thing you need answered>
Assumptions (correct me): <what I'm taking as given to proceed — stated, not baked in silently>
→ Proceed? (or the user corrects)
```

## Anti-rationalization

| You'll think | Reality |
|---|---|
| "I get the gist, I'll just start" | The gist is where wrong assumptions hide. One sentence of restatement catches them — a 10-second question beats a 10-minute wrong build. |
| "I'll infer the missing scope" | Inferring scope the user didn't state is how scope creep and rework begin. State it and confirm. |
| "The request says it works that way, so it does" | Premises are claims, not facts. Grep before you build on one. |

## Note

This skill pairs with the `UserPromptSubmit` hook
[`.claude/hooks/prompt-refiner-inject.py`](../../hooks/prompt-refiner-inject.py), which detects
vague prompts and reminds the agent to run this skill. If you remove the skill, also update or
remove that hook so it doesn't reference a skill that no longer exists.
