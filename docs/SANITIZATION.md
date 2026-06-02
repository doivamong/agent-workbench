# Sanitization & Provenance

This repository is a **domain-stripped export** of the generic layer of a larger,
private single-developer codebase. This document records *how* it was scrubbed, so you
can trust the result and reproduce the check.

## What was removed

| Class | Examples removed | Replacement |
|---|---|---|
| Absolute paths | `<DRIVE>:\<PROJECT>`, `<HOME>\<user>` | `${PROJECT_ROOT}`, relative paths |
| Personal identity | real names, emails, phone numbers | `dev@example.com`, `<YOUR NAME>` |
| Business identity | brand name, domain, registration numbers, GitHub handle | `<project>` |
| Messaging/bot IDs | chat IDs, bot tokens | removed / `<TOKEN>` |
| Domain schema | original table/column/config-key names | generic example names |
| Allow/deny lists | project-specific session-key / file whitelists | illustrative samples |
| Business logic | profit/scoring/pricing formulas | **excluded entirely (trade secret)** |
| Customer data | any real PII | **never present; excluded** |

## What was excluded for license reasons

See [`../THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md). In short: any file that
carried a non-commercial (CC BY-NC) or "commercial license — do not redistribute" origin
was either **re-implemented from first principles** or **omitted**, not copied verbatim.

## How to verify (reproducible)

A generic scanner ships in this repo. Run it with your own private deny-list (kept
**outside** the repo, gitignored) listing the original identifiers you want to be sure
are gone:

```bash
python tools/leak_scan.py . --denylist /path/to/private-denylist.txt --fail-on-find
```

A clean export reports **0 findings**. The deny-list itself is never committed here —
committing your private vocabulary would itself be a leak.

## Honesty note

Manual sanitization is never provably 100%, and the scanner has real blind spots: `leak_scan`
is **line-based**, so an identifier split across two lines — or one with no recognizable shape
that falls below the entropy threshold — can slip past it (see the documented `leak_scan` limits
in [`SECURITY.md`](SECURITY.md)). This export was scanned with the tool above **plus** a
line-by-line read of every ported file, but treat both as tripwires, not proofs. If you spot a
residual identifier, that's a bug — please open an issue (without quoting the sensitive value).
