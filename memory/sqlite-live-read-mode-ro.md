---
name: sqlite-live-read-mode-ro
description: "Default sqlite3.connect(path) opens READ-WRITE; closing can checkpoint the WAL and change the DB file's bytes (hash) even when you only read. Open `file:{path}?mode=ro` (uri=True) for a truly non-destructive read."
metadata: 
  type: feedback
---

`sqlite3.connect("file.db")` opens the database **read-write** by default. If the DB is in WAL
mode, merely opening and closing a connection — even one you only `SELECT` from or `.backup()` —
can trigger a WAL checkpoint on close, rewriting the main file. The data is intact, but the file's
bytes (and therefore its hash) change. A backup / audit / DR-drill that "only reads" then reports
the source file as modified.

**Why:** "I only read it" is false at the file-byte level; a downstream hash / integrity check then
fires a false alarm, or a backup pipeline mutates the very file it is meant to protect.

**How to apply:** for a genuinely non-destructive read, open read-only via URI:
`sqlite3.connect(f"file:{path}?mode=ro", uri=True)`. Use this in any tool that inspects a live DB it
must not touch. (`sqlite3` is stdlib, so this fits the stdlib-only core.)
