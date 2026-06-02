# Third-Party Notices

The code in this repository is **original** (MIT, see `LICENSE`) or **independently
re-implemented**. To the best of the author's knowledge it does **not include substantial
verbatim source code** from third-party projects.

The projects below influenced the *design* (patterns and ideas, not code). They are credited
here as a courtesy, and where a specific file adapts an upstream idea it also cites it inline
(e.g. `tools/affected_tests.py` notes it was inspired by `codegraph` and re-implemented from
scratch with no code copied).

## Design influences — courtesy attribution

| Project | License | What it influenced (idea / pattern only) |
|---|---|---|
| `claudekit` / claudekit-engineer | MIT | Workflow-rule and command-writing structure; the "remind to simplify after a burst of edits" idea behind `post_edit_simplify.py` (independently re-implemented in stdlib Python — no source copied) |
| `mattpocock/skills` | MIT | The "grill / iterative-refine" prompt pattern; TDD slice idea |
| `colbymchenry/codegraph` (© Colby McHenry) | MIT | The "affected tests" selection idea (re-implemented in stdlib `ast`) |
| `anthropics/claude-plugins-official` | MIT | Command-development guidance |
| `Lum1104/Understand-Anything` (© Lum1104) | MIT | Disk-intermediate output protocol (concept) |

These are MIT-licensed; MIT requires preserving the copyright/permission notice only when you
redistribute the licensed *code*. Since no substantial code from these projects is included
here, this courtesy attribution is provided in good faith. If you later vendor any upstream
file verbatim, add its full `LICENSE` text under `licenses/` at that time.

## ⛔ Non-commercial source — deliberately NOT redistributed

| Upstream | License | How it was handled |
|---|---|---|
| `academic-research-skills` | **CC BY-NC 4.0** | Its mode-registry / spectrum+oversight / failure-mode-catalog **expression** is a non-commercial work. A downstream "waiver self-acknowledgement" has **no legal effect** — only the original author can waive. This repo therefore **excludes the verbatim catalog** and **re-authored `skill-registry.md` from first principles** (own naming/columns/format; ideas aren't protected, specific expression is). |

## What was intentionally excluded for license / safety reasons

- The verbatim non-commercial mode-registry / failure-mode catalog (CC BY-NC).
- Any file that carried a "commercial license — do not redistribute" header in the source
  codebase (e.g. a vendored logger): re-implemented cleanly or omitted.
- All project-specific config, data, secrets, and identifiers (see `docs/SANITIZATION.md`).

If you believe something here under-credits your work, please open an issue — attribution
fixes are welcome.
