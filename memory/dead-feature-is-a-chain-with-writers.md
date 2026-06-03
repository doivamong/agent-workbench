---
name: dead-feature-is-a-chain-with-writers
description: "Reader-dead is not writer-stopped: a 'dead' feature is a chain (UI→reader→writer→scheduled task→table→config→test). Deleting by the gone UI leaves a background writer still filling a table. Trace the whole chain — incl. schedulers — before declaring dead."
metadata: 
  type: feedback
---

When a feature looks dead because its UI / read path is gone, the *write* side often is not. A
background writer — a scheduled task / cron / ETL job — can keep populating a table or file that
nothing reads any more. Deleting just the visible reader leaves live dead-weight accruing silently,
and a dead-code sweep that only greps call-sites misses it.

**Why:** "no one reads it" and "nothing writes it" are different claims; conflating them under-
deletes (an orphaned writer keeps running) or over-deletes (a reader whose writer still has other
consumers). This is the false-positive trap a dead-code audit must guard against.

**How to apply:** before declaring a feature dead, trace the full chain — route → service/handler →
**writer** → scheduler registration (Task Scheduler / cron) → table/file → config key → test — and
confirm each link is dead, not just the entry point. Enriches the dead-code-audit cross-checks (a
reader being dead is one signal, never the whole verdict).
