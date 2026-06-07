---
name: github-anchor-slug-double-dash
description: "GitHub heading-anchor slugs turn EACH space into its own dash and strip &/— without collapsing the spaces around them, so `## Status & honesty` -> `#status--honesty` (double dash). A homemade checker doing `re.sub(r'\\s+','-',s)` collapses it and false-flags a valid anchor; trust the real gate, not a hand-rolled slug."
metadata: 
  type: reference
---

GitHub builds a heading's in-page anchor by: lowercasing, **removing** punctuation like `&` and `—`
(em dash) but NOT the spaces around them, then mapping **each remaining space to one `-`**. It does
NOT collapse runs of spaces. So `## Status & honesty` -> `#status--honesty` (the removed `&` leaves
two spaces -> two dashes), and `## Trạng thái & trung thực` -> `#trạng-thái--trung-thực`. Diacritics
are kept as-is.

A homemade anchor-checker that does `re.sub(r"\s+", "-", s)` collapses the double dash to one and
**false-flags a valid anchor as broken** — easy to hit twice in one session on exactly those headings,
both times a false alarm.

**How to apply:** when verifying `[x](#slug)` in-page links resolve, replace each space with a single
dash (do NOT collapse `\s+`), strip `&`/`—`/other punctuation but keep the spaces they sat between.
Better: if the heading text is unchanged, its existing anchor is still valid — don't "fix" a
double-dash anchor, it's correct. Cross-check: the real gate (a link-check / docs test) passing is
stronger evidence than a hand-rolled slug heuristic.
