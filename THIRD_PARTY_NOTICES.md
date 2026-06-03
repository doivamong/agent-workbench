# Third-Party Notices

Most code here is **original** (MIT, see `LICENSE`) or **independently re-implemented**. The one
exception is a single **adapted** file noted under "Adapted source" below, redistributed under its
original permissive license with attribution. Apart from that file, to the best of the author's
knowledge this repo does **not include substantial verbatim source code** from third-party projects.

The projects below influenced the *design* (patterns and ideas, not code). They are credited
here as a courtesy, and where a specific file adapts an upstream idea it also cites it inline
(e.g. `tools/affected_tests.py` notes it was inspired by `codegraph` and re-implemented from
scratch with no code copied).

## Design influences — courtesy attribution

| Project | License | What it influenced (idea / pattern only) |
|---|---|---|
| `claudekit` / claudekit-engineer | MIT | Workflow-rule and command-writing structure; the "remind to simplify after a burst of edits" idea behind `post_edit_simplify.py` (independently re-implemented in stdlib Python — no source copied) |
| `mattpocock/skills` | MIT | The "grill / iterative-refine" prompt pattern; the vertical-slice red-green-refactor framing in `awb-tdd`; the "zoom out one layer before diving in" idea in `awb-research` |
| `colbymchenry/codegraph` (© Colby McHenry) | MIT | The "affected tests" selection idea (re-implemented in stdlib `ast`) |
| `anthropics/claude-plugins-official` | MIT | Command-development guidance; the multi-perspective-planning idea (parallel planners → convergent/divergent/unique merge) in `awb-cook` |
| `github/spec-kit` | MIT | The graduated-oversight / spec-driven build-workflow pattern in `awb-cook` (re-authored in stdlib prose; no source copied) |
| `Lum1104/Understand-Anything` (© Lum1104) | MIT | Disk-intermediate output protocol (concept) |
| `MiniMax-AI/skills` (© MiniMax) | MIT | SKILL.md frontmatter validation idea — block-scalar parser + USE WHEN / DO NOT TRIGGER presence checks in `tools/skill_lint.py` (re-implemented in stdlib; no source copied) |
| `affaan-m/ECC` (© Affaan Mustafa) | MIT | Context-budget auditing idea — component scan, always/sometimes/rarely buckets, and session-start-vs-on-demand split in `tools/check_context_budget.py` (re-implemented in stdlib; no source copied) |

These are MIT-licensed; MIT requires preserving the copyright/permission notice only when you
redistribute the licensed *code*. Since no substantial code from these projects is included
here, this courtesy attribution is provided in good faith. If you later vendor any upstream
file verbatim, add its full `LICENSE` text under `licenses/` at that time.

## Adapted source — included with attribution (Apache-2.0)

One file is a genuine adaptation of an upstream file (not just a design influence), redistributed
under the upstream's permissive license:

| File here | Upstream | License | What was modified |
|---|---|---|---|
| `.claude/agents/silent-failure-hunter.md` | `anthropics/claude-plugins-official` → `pr-review-toolkit/agents/silent-failure-hunter.md` (© Anthropic) | **Apache-2.0** | Kept the 5-dimension error-handling audit structure, severity rubric, output format, and tone; genericized project-specific references (error-id constants, Sentry/Statsig logging names, named examples) into language-neutral guidance. |

The full Apache-2.0 license text is vendored at
[`licenses/claude-plugins-official-pr-review-toolkit-APACHE-2.0.txt`](licenses/claude-plugins-official-pr-review-toolkit-APACHE-2.0.txt).
Apache-2.0 §4 is satisfied: the license is retained, the file carries an attribution header, and the
modifications are stated (here and in the file).

## ⛔ Non-commercial source — deliberately NOT redistributed

| Upstream | License | How it was handled |
|---|---|---|
| `academic-research-skills` | **CC BY-NC 4.0** | Its mode-registry / spectrum+oversight / failure-mode-catalog **expression** is a non-commercial work. A downstream "waiver self-acknowledgement" has **no legal effect** — only the original author can waive. This repo therefore **excludes the verbatim catalog** and **re-authored `skill-registry.md` from first principles** (own naming/columns/format; ideas aren't protected, specific expression is). Several private source skills carried this same `spectrum:`/`oversight:` overlay; the skills derived from them (`awb-stress-test`, `awb-tdd`, `awb-optimize`, `awb-dead-code-audit`, `awb-cook`, `awb-external-ref`) were likewise **re-authored from first principles** with the overlay dropped — concept only, no expression copied. |

## What was intentionally excluded for license / safety reasons

- The verbatim non-commercial mode-registry / failure-mode catalog (CC BY-NC).
- Any file that carried a "commercial license — do not redistribute" header in the source
  codebase (e.g. a vendored logger): re-implemented cleanly or omitted.
- All project-specific config, data, secrets, and identifiers (see `docs/SANITIZATION.md`).

If you believe something here under-credits your work, please open an issue — attribution
fixes are welcome.
