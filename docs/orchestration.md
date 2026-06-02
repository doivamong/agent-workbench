# Orchestration — delegating work to sub-agents

[`sub-agents.md`](sub-agents.md) covers *what* an agent file is. This covers *how* to hand work
to one (or many) well: when delegation pays off, how to brief an agent that can't see your
conversation, and how to get back a result you can act on instead of a wall of text.

## When to delegate (and when not to)

Reach for a sub-agent when one of these is true:

- **Context isolation** — the job produces a lot of intermediate noise (reading 20 files, a long
  search) and you only want the conclusion in your main thread.
- **Independent perspective** — you want a reviewer that did *not* write the code, so it isn't
  anchored on the author's intent (the shipped [`silent-failure-hunter`](../.claude/agents/silent-failure-hunter.md) is this).
- **Parallel fan-out** — several independent sub-tasks can run at once (review N files, research M
  options) and you'll merge the results.
- **Scale beyond one context** — a sweep too large to hold in a single conversation.

Do **not** delegate a quick, single-step task you can do inline — spawning an agent costs a
round-trip and a fresh context. Delegation earns its keep on *breadth* or *independence*, not on
small chores.

## Brief it like it has amnesia (because it does)

A spawned agent does **not** share your conversation, your open files, or your prior reasoning. Its
prompt is the entire world it sees. A good brief is **self-contained**:

- State the **goal** and what "done" looks like in one or two sentences.
- Include the **concrete inputs**: file paths, the command to run, the exact question — not "the
  file we were just looking at".
- Say what to **return** and in what shape (see the status protocol below).
- Note **constraints** (read-only? don't touch X? stay in directory Y?).

A vague brief produces a vague result, and you can't tell whether the agent was wrong or just
under-instructed. The fix is always more specific inputs, not a longer scolding.

## Get back a result you can act on

The agent's final message is the *only* thing handed back — so make it structured. A small,
consistent **status protocol** lets you triage a fan-out at a glance. One that works:

| Status | Means | You then |
|---|---|---|
| `DONE` | finished, result included | use it |
| `CONCERNS` | done, but with caveats worth reading | review the caveats |
| `BLOCKED` | couldn't proceed (missing access, failing precondition) | unblock and re-run |
| `NEEDS-CONTEXT` | the brief was insufficient | add the missing input and re-run |

Ask for the status as the first line of the reply, so a parallel batch is scannable without
opening each one.

## Large outputs: write to disk, return a pointer

When an agent would return something big (a full report, a large diff, structured data), having it
dump everything into its final message bloats *your* context — the opposite of why you delegated.
Instead, have it **write the artifact to a file and return a short status plus the path** (and a
≤500-character summary). You read the file only if the summary says you need to. (This
disk-intermediate pattern is credited to `Lum1104/Understand-Anything`, MIT — see
[THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).)

## Honest limit

This is a convention, not machinery: nothing here enforces that an agent's brief is actually
self-contained or that it honors the status protocol — those are habits you keep. Delegation also
multiplies cost (each agent is its own context); fan out because the work is genuinely parallel or
needs an independent pass, not by reflex.
