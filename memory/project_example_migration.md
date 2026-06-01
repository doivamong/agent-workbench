---
name: project-example-migration
description: Ongoing migration off the legacy job queue; new code must not deepen the dependency.
metadata:
  type: project
---

The project is gradually moving off a legacy job-queue system onto a new one. The migration
is partial and will run for a while.

**Why:** Not derivable from the code — both systems exist in the tree right now, so a reader
can't tell which is the intended direction without this note.

**How to apply:** New features should target the new queue. Don't add new callers of the
legacy queue; if you must touch legacy code, prefer changes that make removal easier later.

Related: [[reference-example-dashboard]]
