# Third-Party Notices

This repository contains original code (MIT, see `LICENSE`) **and** code/ideas that are
ports or derivatives of other open-source projects. This file tracks those obligations.

> ⚠️ **Maintainer checklist before publishing** — do not push public until every row
> below is verified. Some upstream sources carry constraints (attribution, non-commercial)
> that a downstream "waiver self-acknowledgement" **cannot** legally override.

## MIT-licensed sources (attribution required, redistribution OK)

Each of these requires preserving the original copyright + permission notice. Paste the
upstream `LICENSE` text into `licenses/<name>-LICENSE.txt` and confirm before shipping.

| Upstream project | Used for | Status |
|---|---|---|
| `claudekit` / claudekit-engineer | Workflow rules, command-writing patterns | ⬜ verify license text + that no "commercial-license" variant code was copied |
| `mattpocock/skills` | Prompt-refiner "grill" pattern, TDD slice ideas | ⬜ add LICENSE |
| `colbymchenry/codegraph` (© Colby McHenry) | Tool-budget split pattern (concept only) | ⬜ add LICENSE |
| `anthropics/claude-plugins-official` | Command-development guidance | ⬜ add LICENSE |
| `Lum1104/Understand-Anything` (© Lum1104) | Disk-intermediate output protocol (concept) | ⬜ add LICENSE |
| taste-skill | Doc-only cherry-picks | ⬜ add LICENSE |

## ⛔ Non-commercial / restricted sources — DO NOT redistribute as-is

| Upstream | Issue | Required action |
|---|---|---|
| `academic-research-skills` (CC BY-NC 4.0) | The MODE_REGISTRY / spectrum+oversight / failure-mode-catalog **formats** are derivative of a **non-commercial** work. A self-claimed "waiver" by a downstream user has **no legal effect** — only the original author can waive. | Pick one: (1) obtain a written waiver from the upstream author; (2) **re-implement from first principles** — your own naming/columns/format; ideas aren't protected, specific expression is; or (3) exclude entirely. **This repo currently chooses (2)+(3): the registry-style index here was re-authored from scratch, and the verbatim catalog is excluded.** |
| Any file that carried a "commercial license — do not redistribute" comment in the source codebase (e.g. a vendored logger, an orchestration rule) | Cannot be shipped verbatim. | Rewrite the functionality independently, or omit. This repo **omits** those and ships clean re-implementations where valuable. |

## What was intentionally excluded for license safety

- The verbatim non-commercial mode-registry / failure-mode catalog.
- Any vendored file bearing a commercial-license header.
- All project-specific config, data, and secrets (see `docs/SANITIZATION.md`).
