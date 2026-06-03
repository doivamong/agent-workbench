# License classification matrix

A quick map from a source's licence to what you may do with its **code** (porting expression),
and the obligations that come with it. This is a seatbelt for routine decisions — **not legal
advice**. When the value is high or the licence is unclear, escalate to a human.

## Categories → reuse rights (for *porting code*)

| Category | Examples | Port code into a permissive project? | Obligation if you port |
|---|---|---|---|
| **permissive** | MIT, BSD-2/3, Apache-2.0, ISC | Yes | Keep the licence text + copyright; add a `THIRD_PARTY_NOTICES.md` entry. Apache-2.0 also has a patent grant + NOTICE file. |
| **public-domain** | CC0, Unlicense, WTFPL | Yes | None required (attribution still courteous). |
| **weak-copyleft** | LGPL, MPL-2.0, EPL, CDDL | File-scoped: usually OK if you keep changes to those files open | Disclose modifications to the covered files; keep their licence. |
| **strong-copyleft** | GPL-2.0, GPL-3.0 | No (would force your whole project to GPL) | Don't port into a permissive repo — **salvage the concept** instead. |
| **network-copyleft** | AGPL-3.0, SSPL | No (triggers even over a network service) | Same — salvage, don't port. |
| **proprietary** | "All rights reserved", commercial, EULA | No | None permits redistribution — salvage the concept or stop. |
| **no-license** | repo with no LICENSE file | No | Absence of a licence = **all rights reserved by default**. Treat as proprietary. |
| **unknown** | custom / unclear / conflicting | No until resolved | Don't guess. Identify it, or salvage the concept. |

## The decision in one line

- **Permissive / public-domain** → port is fine *with the notice*.
- **Any copyleft** → porting drags its obligations onto your project; prefer **salvage the concept**.
- **Proprietary / no-licence / unknown** → **salvage the concept, or stop and ask a human.**

## Salvage-the-concept (the always-available path)

Ideas and techniques are not copyrightable — only their *expression* is. So you may always:

1. Read the source for the **technique**, not the text.
2. Close it. Re-implement from your own understanding, in your own structure and naming.
3. Don't reproduce its expression — its literal code, comment wording, or distinctive structure.
4. Note in the commit that it's a first-principles re-author copying no expression.

A genuine re-author carries **no** licence obligation. (This is exactly how the skills in
this kit were distilled from a private source.)

## Caveats

- **Copyright ≠ patents.** Clearing the copyright path does not clear a patent that may read on the
  technique. Separate question; separate (legal) advice.
- **Detection is heuristic.** A LICENSE file can be wrong, dual, or contradicted by per-file SPDX
  headers. Per-file headers win over a repo-root guess.
- **Private repos:** even an MIT-labelled *private* repo may not grant you the right to use it —
  confirm you have access rights before adopting.
