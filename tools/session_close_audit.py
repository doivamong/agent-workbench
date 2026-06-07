#!/usr/bin/env python3
"""Audit whether a working tree is safe to close at the end of a session (stdlib + git/gh, read-only).

The pain this guards: after a long session you can't remember whether anything is still dangling —
work not committed, commits not pushed, a PR not merged, or stale branches piling up — so you either
close anxiously or comb through git by hand every time. This reporter answers one question in plain
language: "is it safe to close this window, and what's left to clean?"

It mutates NOTHING. It reads git and (if present) the `gh` CLI, classifies what it finds, and prints
the exact cleanup commands for YOU to run — it never commits, pushes, merges, or deletes a branch.

  python tools/session_close_audit.py             # full report + verdict
  python tools/session_close_audit.py --exit-code # also exit 1 if work could be LOST on close

The risk model (why some findings BLOCK and others only WARN) turns on one question — "would closing
the window LOSE this?":

  * BLOCK  uncommitted changes, or commits not on any remote. These live only in this working tree;
           close the window and they are at risk. The verdict is "not safe to close yet".
  * WARN   open PRs, and stale local branches (merged or squash-merged). These are already on the
           server, so closing loses nothing — they are hygiene, surfaced with a cleanup command.

Squash-merge detection (the trap a naive `git branch --merged` misses): GitHub's squash gives the
merge a NEW commit hash, so the branch's original tip is never an ancestor of `main` and
`--no-merged` lists it as if it held unmerged work. We cross-check the branch's commit SUBJECT
against `origin/main`'s history (ignoring a trailing ` (#123)` that squash appends): a match means
the work IS in main and the branch is safe to delete with `-D`, not real work you'd lose.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

# Squash-merge appends " (#123)" to the PR title; strip it so a branch subject matches its main entry.
_PR_SUFFIX = re.compile(r"\s*\(#\d+\)\s*$")
# How far back to read main's history when matching squash-merged subjects. Bounded so the call is
# cheap on a large repo; a branch whose work landed thousands of commits ago is not "recent cleanup".
_MAIN_LOG_LIMIT = 400


def _norm_subject(subject: str) -> str:
    """A commit subject with any trailing PR-number suffix removed, for squash-merge matching."""
    return _PR_SUFFIX.sub("", subject).strip()


# ----------------------------------------------------------------------------------------------
# Pure classification (no I/O — unit-testable). All git/gh access is in the gather/* helpers below.
# ----------------------------------------------------------------------------------------------
def classify_branches(
    merged: list[str],
    no_merged: list[str],
    remote_gone: set[str],
    main_subjects: set[str],
    branch_subject: dict[str, str],
) -> dict:
    """Sort local branches into delete-safe / squash-deletable / real-work. Pure.

    - ``merged``: local branches whose tip IS an ancestor of origin/main -> delete with ``-d``.
    - ``no_merged``: local branches that are NOT -> each is either squash-merged (safe ``-D``) or
      genuine unmerged work, decided by whether its subject is in ``main_subjects`` AND its remote
      tracking branch is gone (a live remote means it may still be in flight, not abandoned).
    ``main_subjects`` and the values of ``branch_subject`` are normalised here, so callers may pass
    raw subjects — the squash suffix is handled inside.
    """
    norm_main = {_norm_subject(s) for s in main_subjects}
    deletable_squash, real_work = [], []
    for b in no_merged:
        landed = _norm_subject(branch_subject.get(b, "")) in norm_main
        if landed and b in remote_gone:
            deletable_squash.append(b)
        else:
            real_work.append(b)
    return {
        "deletable_safe": list(merged),
        "deletable_squash": deletable_squash,
        "real_work": real_work,
    }


def build_verdict(
    uncommitted: list[str],
    unpushed: int,
    tracked: bool,
    open_prs: list[dict],
    branches: dict,
) -> dict:
    """Turn the gathered state into a safe/blocked verdict + reason lists. Pure.

    BLOCK = things that exist only locally and would be lost on close. WARN = already-on-server
    hygiene. ``tracked`` is False when the current branch has no upstream, which colours the
    unpushed message (commits measured against origin/main rather than a real upstream).
    """
    blockers, warnings = [], []

    if uncommitted:
        blockers.append(f"{len(uncommitted)} uncommitted change(s) in the working tree")
    if unpushed:
        where = "the current branch" if tracked else "the current branch (no upstream — never pushed)"
        blockers.append(f"{unpushed} commit(s) on {where} not on any remote")

    if open_prs:
        warnings.append(f"{len(open_prs)} open PR(s) — already on the server (run automerge_status.py to check they merge)")
    if branches["real_work"]:
        warnings.append(f"{len(branches['real_work'])} local branch(es) with work not in main — review before deleting")
    junk = branches["deletable_safe"] + branches["deletable_squash"]
    if junk:
        warnings.append(f"{len(junk)} stale local branch(es) safe to delete")

    return {"safe": not blockers, "blockers": blockers, "warnings": warnings}


# ----------------------------------------------------------------------------------------------
# I/O gather helpers (isolated so tests stub them). Each fails soft: a missing tool / git error
# degrades that one finding to "unknown" rather than crashing the whole audit.
# ----------------------------------------------------------------------------------------------
def _git(args: list[str]) -> str:
    """Run a git command, return stdout (stripped). Raises on git failure — callers handle it."""
    return subprocess.check_output(["git", *args], encoding="utf-8", stderr=subprocess.DEVNULL).strip()


def _strip_branch(line: str) -> str:
    """A `git branch` line ('* main', '+ wt', '  feat') -> the bare branch name."""
    return line.lstrip("*+ ").strip()


def gather_uncommitted() -> list[str]:
    return [ln for ln in _git(["status", "--porcelain"]).splitlines() if ln.strip()]


def gather_current(default_base: str = "origin/main") -> dict:
    """Current branch, its upstream (or None), and commits not on any remote."""
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    try:
        upstream = _git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
        tracked = True
        base = upstream
    except subprocess.CalledProcessError:
        upstream, tracked, base = None, False, default_base
    try:
        unpushed = int(_git(["rev-list", "--count", f"{base}..HEAD"]) or "0")
    except (subprocess.CalledProcessError, ValueError):
        unpushed = 0
    return {"branch": branch, "upstream": upstream, "tracked": tracked, "unpushed": unpushed}


def gather_branches(base: str = "origin/main") -> dict:
    """Everything classify_branches needs: merged/no-merged locals, remote-gone set, subjects."""
    current = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    skip = {current, "main", base.split("/")[-1]}

    def _locals(flag: str) -> list[str]:
        names = [_strip_branch(ln) for ln in _git(["branch", flag, base]).splitlines() if ln.strip()]
        return [n for n in names if n and n not in skip]

    merged = _locals("--merged")
    no_merged = _locals("--no-merged")

    remote = {_strip_branch(ln).split("/", 1)[-1]
              for ln in _git(["branch", "-r"]).splitlines() if "HEAD" not in ln and ln.strip()}
    remote_gone = {b for b in no_merged if b not in remote}

    branch_subject = {}
    for b in no_merged:
        try:
            branch_subject[b] = _git(["log", "-1", "--format=%s", b])
        except subprocess.CalledProcessError:
            branch_subject[b] = ""

    try:
        main_subjects = set(_git(["log", base, f"-n{_MAIN_LOG_LIMIT}", "--format=%s"]).splitlines())
    except subprocess.CalledProcessError:
        main_subjects = set()

    return {
        "merged": merged,
        "no_merged": no_merged,
        "remote_gone": remote_gone,
        "main_subjects": main_subjects,
        "branch_subject": branch_subject,
    }


def gather_worktrees() -> int:
    """How many git worktrees share this .git. >1 means separate working trees exist — their files
    are isolated but `.git/refs` and `.git/config` are still SHARED, so a commit can still land on a
    branch another worktree holds. Fails soft to 1 (treat as single tree) on any error."""
    try:
        lines = _git(["worktree", "list", "--porcelain"]).splitlines()
        return max(1, sum(1 for ln in lines if ln.startswith("worktree ")))
    except subprocess.CalledProcessError:
        return 1


def gather_open_prs() -> list[dict] | None:
    """Open PRs via gh, or None if gh is unavailable/errors (the PR check then degrades to unknown)."""
    try:
        out = subprocess.check_output(
            ["gh", "pr", "list", "--state", "open", "--json", "number,title,url,headRefName,autoMergeRequest"],
            encoding="utf-8", stderr=subprocess.DEVNULL,
        )
        return json.loads(out)
    except (FileNotFoundError, subprocess.CalledProcessError, json.JSONDecodeError):
        return None


# ----------------------------------------------------------------------------------------------
# Reporting
# ----------------------------------------------------------------------------------------------
def _format_report(state: dict) -> str:
    """Human-readable report from the gathered + classified state."""
    verdict = state["verdict"]
    cur, branches, prs = state["current"], state["branches"], state["open_prs"]
    out: list[str] = []

    out.append("Session close-out audit (read-only - nothing was changed)")
    out.append("")

    # 1. Uncommitted
    n = len(state["uncommitted"])
    out.append(f"1. Uncommitted changes : {n if n else 'none'}")
    if n:
        out.append("     -> commit them, or `git stash` to set aside (these exist only here).")

    # 2. Unpushed
    out.append(f"2. Unpushed commits    : {cur['unpushed']} on '{cur['branch']}'"
               + ("" if cur["tracked"] else " (no upstream — never pushed)"))
    if cur["unpushed"]:
        out.append("     -> push them; until pushed they live only in this working tree.")

    # 3. Open PRs
    if prs is None:
        out.append("3. Open PRs            : unknown (the `gh` CLI is unavailable)")
    else:
        out.append(f"3. Open PRs            : {len(prs) if prs else 'none'}")
        for p in prs or []:
            auto = "auto-merge ON" if p.get("autoMergeRequest") else "auto-merge OFF"
            out.append(f"     #{p.get('number')} {p.get('title', '')}  [{auto}]")

    # 4. Stale branches
    safe, squash, real = branches["deletable_safe"], branches["deletable_squash"], branches["real_work"]
    out.append(f"4. Stale local branches: {len(safe) + len(squash)} deletable, {len(real)} need review")
    if safe:
        out.append(f"     merged (delete with -d): {' '.join(safe)}")
        out.append(f"       git branch -d {' '.join(safe)}")
    if squash:
        out.append(f"     squash-merged, already in main (delete with -D): {' '.join(squash)}")
        out.append(f"       git branch -D {' '.join(squash)}")
    if real:
        out.append(f"     work NOT in main — review before deleting: {' '.join(real)}")

    out.append("")
    if verdict["safe"]:
        out.append("VERDICT: SAFE TO CLOSE — nothing committed-but-unpushed or uncommitted would be lost.")
    else:
        out.append("VERDICT: NOT SAFE TO CLOSE YET - these would be lost on close:")
        for b in verdict["blockers"]:
            out.append(f"  - {b}")
    for w in verdict["warnings"]:
        out.append(f"  (cleanup) {w}")

    # Concurrency caution: shown only when there IS a write to suggest (a ship to clear blockers, or
    # a branch to delete). We do NOT claim to detect a second session in THIS tree — the per-worktree
    # lock holds only the newest session, so "lock is alive" is true in normal single-session use and
    # would false-alarm every run. The reliable, false-alarm-free signal is the worktree COUNT; the
    # rest is a reminder to verify, because two sessions sharing a tree is the dangerous default.
    has_write = (not verdict["safe"]) or branches["deletable_safe"] or branches["deletable_squash"]
    if has_write:
        out.append("")
        out.append("Before you clean up or ship - concurrent-session safety:")
        out.append(f"  Worktrees sharing this .git: {state['worktrees']}"
                   + ("  (separate trees: files isolated, but refs/config still SHARED)"
                      if state["worktrees"] > 1 else ""))
        out.append("  Two sessions on one tree race HEAD/index and can sweep or corrupt work.")
        out.append("  -> Verify the live branch first:  git branch --show-current && git status --short")
        out.append("  -> If another session shares this tree, do NOT run the cleanup/ship steps here;")
        out.append("     land via  git push + gh pr create --head <branch>  (no HEAD/tree touch),")
        out.append("     and defer branch deletion. See awb-session-close (Concurrent sessions).")
    return "\n".join(out)


def audit() -> dict:
    """Gather + classify the whole repo state into one dict. Isolated so tests can assemble it."""
    uncommitted = gather_uncommitted()
    current = gather_current()
    raw = gather_branches()
    branches = classify_branches(
        raw["merged"], raw["no_merged"], raw["remote_gone"], raw["main_subjects"], raw["branch_subject"]
    )
    open_prs = gather_open_prs()
    verdict = build_verdict(
        uncommitted, current["unpushed"], current["tracked"], open_prs or [], branches
    )
    return {
        "uncommitted": uncommitted,
        "current": current,
        "branches": branches,
        "open_prs": open_prs,
        "worktrees": gather_worktrees(),
        "verdict": verdict,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--exit-code", action="store_true",
                        help="exit 1 if anything would be LOST on close (uncommitted / unpushed work)")
    args = parser.parse_args(argv)

    try:
        _git(["rev-parse", "--git-dir"])
    except (FileNotFoundError, subprocess.CalledProcessError):
        sys.stderr.write("session_close_audit: not a git repository (or git is not installed).\n")
        return 2

    # A fetch --prune makes the remote-gone / merged checks reflect reality, but it is a network
    # write to refs; keep the tool read-only-to-YOUR-work and best-effort here (offline still works).
    try:
        subprocess.run(["git", "fetch", "--prune", "--quiet"], check=False, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        pass

    state = audit()
    print(_format_report(state))
    return 1 if (args.exit_code and not state["verdict"]["safe"]) else 0


if __name__ == "__main__":
    sys.exit(main())
