---
name: awb-install-and-verify
description: >
  WHAT: drive the kit's own installer in plain language — wire the safety hooks into a
  project, then run the real --doctor verifier and explain, honestly, what now protects
  the user and what it does NOT.
  USE WHEN: a user wants to set up or check the workbench's guards ("install the
  workbench", "set up the hooks", "are my guards actually on?", "did the install
  work?", "is the dangerous-command block working?").
  DO NOT TRIGGER: building a new feature/hook (that's a plan-then-code skill); editing
  settings.json by hand (this skill only ever calls install.py); a general "is my code
  good?" review (that's awb-review).
tier: workflow
---

# Install the workbench and prove the guards are on

> **Announce on activation:** "Using awb-install-and-verify — I'll wire the hooks, then run --doctor and tell you exactly what's protected."

The persona this kit serves often can't read a stack trace or a settings file. So setup
must end in a plain-language, *truthful* answer to one question: "which guards are on now,
and which are not?" The only honest source for that answer is the kit's own `--doctor`,
which runs the guards and reports back. This skill makes the agent run it and relay it —
never narrate protection it hasn't proven.

## Scope

- **Does:** run `install.py --merge-settings` to wire the hooks, run `install.py --doctor`
  to verify them, and translate the verifier's output into plain language (what's PROVEN,
  what's only INSTALLED, what failed and how to fix it).
- **Does NOT:** hand-edit `.claude/settings.json` (only `install.py` touches it); claim a
  hook *works* when `--doctor` only proves it is wired; call any tool that isn't installed
  in the target project (see Recovery). It is a bypassable exemplar, not a gate.

## Process

1. **Wire the hooks.** Run `python install.py <project-path> --merge-settings`, where
   `<project-path>` is the **adopter project** (an external path). (Skip if the user only wants
   to verify an existing install.) Note: `install.py` refuses to install into the kit repo
   itself, so do **not** use `.` here — only `--doctor` (step 2) accepts `.`.
2. **Verify — run the real doctor.** Run `python install.py <project-path> --doctor` (here `.`
   *is* allowed, to verify the kit's own wiring). Read-only; it launches the wired guards and
   reports. **Inside an adopter project** (the kit was installed there, you're not in the kit
   folder), prefer `python tools/doctor.py` — the same verifier, copied in with the kit, so the
   user can re-check "are my guards still on?" from their own repo. Fall back to
   `install.py <project-path> --doctor` from the kit folder if `tools/` wasn't installed.
3. **HARD GATE: doctor must exit 0.** If it prints any `FAIL`, the guards are **not**
   protecting the user yet — relay the doctor's own `Fix:` line in plain language and stop.
   Do **not** tell the user they're protected. A green-looking summary you didn't read is
   not proof.
4. **Relay the result honestly — read the doctor output, assert nothing beyond it.**
   - `PROVEN [name]` → that guard was actually exercised and worked. Today only
     `block_dangerous.py` is PROVEN: it really blocked a dangerous command. Say plainly it
     "catches common destructive commands, but is not a security boundary — a determined
     command can still get past it."
   - `INSTALLED [name]` → wired and its interpreter runs, but its behaviour was **not**
     tested. Say "set up and ready, but I haven't watched it do its job" — never upgrade an
     INSTALLED to "working".
5. **Tell them to restart.** The doctor proves the scripts run on this machine, **not** that
   the running session loaded them. Tell the user to restart Claude Code (or start a new
   session) so the hooks take effect.

## Recovery (owner-scoped, minimal)

If the user asks "is anything exposed? / undo the phone/LAN exposure / am I locked out?":
the exposable surface (`ops/*`, `ui/web/`, `set_password.py`) is **not** in the installer's
`COPY_MAP`, so in a project you installed the kit *into*, it isn't there at all. Answer
plainly: "those features aren't installed in your project, so there's nothing of theirs to
expose." Only route to tools that `--doctor`/the manifest show are actually present; if a
step needs a tool that isn't installed, explain the manual step rather than calling a file
that doesn't exist.

## Anti-rationalization

| You'll think | Reality |
|---|---|
| "The summary said all passed, I'll just say you're protected" | Read the per-hook lines. Most are INSTALLED, not PROVEN — saying "protected" oversells what was tested. |
| "Close enough to call this hook working" | INSTALLED ≠ working. The honest word is "wired"; only `--doctor`'s PROVEN earns "working". |
| "I'll skip the restart note" | Without a restart the user's live session may not have the hooks at all — the guards look on but aren't. |

## See also

The plain-language, user-facing walkthrough — install, uninstall (safety model), and a
troubleshooting guide — is the single source in [`docs/getting-started.md`](../../../docs/getting-started.md).
Point the user there for the full prose; this skill is the agent's playbook for *driving* the installer.
