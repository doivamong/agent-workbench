"""Make the kit's modules importable from tests without packaging."""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# "" so ``import install`` (a repo-root module) resolves, plus the kit's source dirs.
for _p in ("", "scripts", "tools", ".claude/hooks/scripts", ".claude/hooks/lib"):
    sys.path.insert(0, str(ROOT / _p))


# Repo-location git env vars: when git runs a hook it EXPORTS these pointing at the active
# repo, so a child `git` invoked by a test (with cwd=<temp repo>) would honour them and operate
# on the WRONG repo instead of auto-discovering from its cwd. Names per `git help environment`.
_GIT_LOCATION_VARS = (
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY", "GIT_NAMESPACE", "GIT_PREFIX",
)


@pytest.fixture(autouse=True)
def _isolate_git_env(monkeypatch):
    """Strip inherited repo-location GIT_* from the env for EVERY test (autouse, suite-wide).

    Defends against the worktree GIT_DIR-leak trap: when the suite runs from a commit hook in a
    LINKED worktree, git sets GIT_DIR/GIT_WORK_TREE to that worktree's gitdir for the hook. A
    test that runs `git init` / `git config` / `git add` (via subprocess with cwd=<temp repo>)
    would then honour the inherited GIT_DIR and write into the SHARED .git/config — flipping
    core.bare, overwriting user.name/email, corrupting the repo for every worktree. Deleting
    these makes every child git auto-discover from its cwd, so a `git commit` from a worktree is
    safe. (Supersedes the per-file _clean_git_env in test_ops_admin_web.py.) Does NOT touch
    GIT_EXEC_PATH / GIT_SSH / author-identity vars — only the "which repo" pointers.
    """
    for _k in _GIT_LOCATION_VARS:
        monkeypatch.delenv(_k, raising=False)
