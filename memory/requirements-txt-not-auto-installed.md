---
name: requirements-txt-not-auto-installed
description: "A new import + a requirements.txt bump is NOT deployed: nothing auto-runs pip in the prod venv, so the code raises ModuleNotFoundError only in production until someone installs it there. Treat the manifest edit and the environment install as two separate acts; name the deploy step in the commit."
metadata: 
  type: feedback
---

Adding a dependency is two acts, and it's easy to do only the first: (1) `import newlib` plus adding it
to `requirements.txt` (the manifest), and (2) actually `pip install` it into the **deployed**
virtualenv. A file watcher / auto-reload restarts the app on a code change but does **not** install
packages, so the new import works on your machine and raises `ModuleNotFoundError` **only in
production** until someone installs it in the prod venv.

**Why:** the manifest edit feels like "adding the dependency," and local dev already has the package,
so the gap is invisible until prod crashes — a deploy-step omission disguised as a code bug.

**How to apply:** treat a manifest bump and an environment install as separate steps; when a commit
adds a dependency, state the deploy action in the commit body (e.g. "run `pip install -r
requirements.txt` in the prod venv"). For a kit whose reusable core is stdlib-only this bites mainly in
`examples/` and in users' own projects — still worth flagging at the boundary.
