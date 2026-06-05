"""ops/ — operational tooling for working ON the agent-workbench repo itself.

Stdlib-only, cross-platform CLIs (and a callable API the opt-in ``ui/web`` admin layer
reuses): dashboard process control, release packaging, and working-tree snapshots. These
are repo-operation tools — they are NOT part of ``install.py``'s payload (they operate on
this repo, not on an adopter's project), and they are not counted among the kit's
"standalone tools" (which are the reusable analysis tools under ``tools/``).
"""
