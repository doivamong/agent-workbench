---
name: awb-uninstall
description: >
  WHAT: drive the kit's own uninstaller in plain language — show what would be removed
  first (dry-run), get an explicit yes, then remove, and say honestly what is KEPT (the
  files you edited) rather than claiming a clean wipe.
  USE WHEN: a user wants to take the workbench back out of a project ("remove
  agent-workbench", "uninstall the kit", "take the hooks out", "undo the install").
  DO NOT TRIGGER: installing or verifying guards (that's awb-install-and-verify);
  hand-deleting files yourself (this skill only ever calls uninstall.py); a general "is
  my code good?" review (that's awb-review).
tier: workflow
---

# Uninstall the workbench, honestly

> **Announce on activation:** "Using awb-uninstall — I'll show you exactly what would be removed first, then remove it only once you confirm."

The persona this kit serves often can't read a manifest or diff a settings file, so they
can't tell a clean uninstall from one that quietly deleted work they'd changed. The only
honest way to remove the kit is to **show the plan before touching anything**, get a clear
yes, and then state plainly what was removed and what was *kept*. `uninstall.py` is built
for exactly this — it is dry-run by default and never deletes a file you edited. This skill
makes the agent use it that way instead of improvising file deletions.

## Scope

- **Does:** run `uninstall.py <project>` (dry-run) to get the removal plan, translate it
  into plain language, get an explicit confirm, then run `uninstall.py <project> --yes` and
  relay what was removed vs. kept.
- **Does NOT:** hand-delete any file (only `uninstall.py` removes anything); remove files
  you edited since install (those are KEPT by design — see Honesty); guess what to remove
  when there's no installer-manifest (`uninstall.py` refuses, and so should you). It is a
  bypassable exemplar, not a gate.

## Precondition

`uninstall.py` lives in the **kit folder**, not in the project it was installed into. Run it
from the kit checkout, pointing at the adopter project:
`python uninstall.py <project-path>`. (Same precondition the install skill documents — the
uninstaller is never copied into adopter projects.)

## Process

1. **Dry-run first — show, don't touch.** Run `python uninstall.py <project-path>`. With no
   `--yes` it changes nothing; it prints the plan: which files *would be removed*, which are
   *KEPT (modified since install)*, the `settings.json` revert, and the `.gitignore` cleanup.
2. **Relay the plan in plain language.** Tell the user, in their terms: how many files would
   be removed, which (if any) are kept because they edited them, and that the hooks will be
   unwired from `settings.json`. Don't paraphrase a plan you didn't read — read the actual
   output.
3. **HARD GATE: explicit confirm before applying.** Ask the user to confirm they want to
   proceed. Do **not** run `--yes` on assumption. If they hesitate or say "what gets kept?",
   answer from the dry-run output before going further.
4. **Apply.** Once confirmed, run `python uninstall.py <project-path> --yes`. Relay the
   result honestly: N files removed, M kept (modified), empty dirs pruned.
5. **No manifest → stop, don't guess.** If `uninstall.py` reports no installer-manifest, it
   refuses to pattern-delete blindly — relay that and the remedy it prints (re-run install to
   regenerate the manifest, or remove by hand). Never substitute your own `rm`.

## Honesty (say this, don't soften it)

- **"Remove" does not mean "wipe everything."** A file you edited since install (its bytes no
  longer match the kit's recorded sha256) is **KEPT, not deleted** — uninstall never destroys
  your changes. Say which files were kept and that they're left for the user to remove by hand
  if they truly want them gone.
- Only an **untouched** install → uninstall leaves `git status` fully clean. If the user
  edited copied files, the tree won't be empty afterward — and that's correct, not a bug.
- The uninstaller reverts only the hook commands install added; hooks the user added
  themselves survive. Don't claim a blanket "settings.json restored to factory."

## Anti-rationalization

| You'll think | Reality |
|---|---|
| "They said uninstall, I'll just run `--yes`" | Dry-run first and show the plan. `--yes` without a confirmed plan can surprise them with what was (or wasn't) removed. |
| "I'll just `rm` the kit files myself, it's faster" | Then you bypass the sha-check that keeps their edited files — exactly the safety this skill exists for. Only `uninstall.py` removes anything. |
| "No manifest, I'll figure out what to delete" | That's the blind pattern-delete `uninstall.py` refuses on purpose. Relay the refusal; never guess. |
| "I'll say it removed everything" | If any file was edited it was KEPT. Saying "removed everything" is the dishonest over-promise this skill forbids. |
