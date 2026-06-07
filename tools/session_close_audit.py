#!/usr/bin/env python3
"""Audit whether a working tree is safe to close at the end of a session (stdlib + git/gh).

The pain this guards: after a long session you can't remember whether anything is still dangling -
work not committed, commits not pushed, a stash forgotten, a rebase half-finished, a PR not merged,
or stale branches piling up - so you either close anxiously or comb through git by hand. This
reporter answers one question in plain language: "is it safe to close this window, and what's left
to clean?"

It is read-only TO YOUR WORK: it never commits, pushes, merges, or deletes a branch - it reports
and prints the exact cleanup commands for YOU to run. It DOES run `git fetch --prune` once (a network
call that refreshes remote-tracking refs) unless you pass --no-fetch.

  python tools/session_close_audit.py             # full report + verdict
  python tools/session_close_audit.py --exit-code # also exit 1 if work could be LOST on close
  python tools/session_close_audit.py --no-fetch   # skip the network fetch (offline)

The risk model (why some findings BLOCK and others only WARN) turns on one question - "would closing
the window LOSE this?":

  * BLOCK  uncommitted changes; commits not on any remote; an in-progress rebase/merge/cherry-pick;
           detached-HEAD commits. These are local-only or mid-operation - close and they are at risk
           (or the verdict can't be measured). The verdict is "not safe to close yet".
  * WARN   a stash, open PRs, and stale local branches. A stash and server-side refs persist on
           disk, so closing loses nothing immediately - they are hygiene, surfaced with a command.

Squash/rebase-merge detection (the trap a naive `git branch --merged` misses): a squash gives the
merge a NEW commit hash, so the branch's tip is never an ancestor of `main` and `--no-merged` lists
it as if it held unmerged work. We do NOT guess from the commit subject (two unrelated commits can
share a subject - that would force-delete real work). Instead we ask `git cherry origin/main
<branch>`: only when EVERY patch on the branch is already present upstream do we mark it safe to
delete with -D. A branch whose changes are not provably contained falls to "review before deleting".
Limit: `git cherry` is patch-id based, so a MULTI-commit branch combined into one squashed commit
will not show as contained and is conservatively kept for review (verify, then delete manually) -
the tool fails SAFE rather than recommend a force-delete it cannot prove.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

# Branch names safe to embed verbatim in a printed shell command (no spaces / shell metachars).
_SAFE_BRANCH = re.compile(r"^[A-Za-z0-9._/-]+$")
# Control chars to strip from externally-controlled text (gh PR titles) before echoing it.
_CTRL = re.compile(r"[\x00-\x1f\x7f]")
# git's pseudo-branch lines in `git branch` output (detached HEAD / bisect), not real branches.
_PSEUDO_HINTS = ("HEAD detached", "no branch")
# In-progress operations, by the marker path under .git that signals them.
_IN_PROGRESS = [
    ("rebase-merge", "rebase"), ("rebase-apply", "rebase"),
    ("MERGE_HEAD", "merge"), ("CHERRY_PICK_HEAD", "cherry-pick"), ("REVERT_HEAD", "revert"),
]


# ----------------------------------------------------------------------------------------------
# Low-level git I/O (one chokepoint; fails soft so a single git error never crashes the audit).
# ----------------------------------------------------------------------------------------------
def _git(args: list[str]) -> str:
    """Run a git command, return stdout (stripped). Decodes leniently so a non-UTF-8 byte in a
    branch name / path degrades to a replacement char instead of crashing (fail-soft contract).
    Raises CalledProcessError on git's own non-zero exit - callers handle that."""
    return subprocess.check_output(
        ["git", *args], encoding="utf-8", errors="replace", stderr=subprocess.DEVNULL
    ).strip()


def _ref_exists(ref: str) -> bool:
    """True if `ref` resolves to a commit (e.g. 'origin/main', 'origin/<branch>')."""
    try:
        _git(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"])
        return True
    except subprocess.CalledProcessError:
        return False


def _count(rev_range: str):
    """Commit count for `rev_range`, or None if it can't be measured (unresolvable ref).
    None is a SENTINEL meaning 'unknown' - never coerced to 0, which would read as a clean result."""
    try:
        return int(_git(["rev-list", "--count", rev_range]) or "0")
    except (subprocess.CalledProcessError, ValueError):
        return None


def _strip_branch(line: str) -> str:
    """A `git branch` line ('* main', '+ wt', '  feat') -> the bare branch name."""
    return line.lstrip("*+ ").strip()


def _is_pseudo(name: str) -> bool:
    """True for git's pseudo-branch lines like '(HEAD detached at abc123)' / '(no branch)'.
    Only matches the parenthesised pseudo forms - a real branch legally named '(weird)' is kept."""
    return name.startswith("(") and any(h in name for h in _PSEUDO_HINTS)


# ----------------------------------------------------------------------------------------------
# Pure classification (no I/O - unit-testable).
# ----------------------------------------------------------------------------------------------
def classify_branches(merged: list[str], no_merged: list[str], contained: set[str]) -> dict:
    """Sort local branches into delete-safe / squash-deletable / real-work. Pure.

    - ``merged``: tip IS an ancestor of origin/main -> delete with ``-d``.
    - ``no_merged`` whose every patch is already upstream (``contained``, decided by `git cherry`
      in gather_branches) -> squash/rebase-merged -> delete with ``-D``.
    - everything else -> real_work (changes NOT provably in main; review before deleting).
    """
    deletable_squash, real_work = [], []
    for b in no_merged:
        (deletable_squash if b in contained else real_work).append(b)
    return {"deletable_safe": list(merged), "deletable_squash": deletable_squash, "real_work": real_work}


def build_verdict(uncommitted: list[str], current: dict, stash: int,
                  in_progress, open_prs: list[dict], branches: dict) -> dict:
    """Turn gathered state into a safe/blocked verdict + reason lists. Pure.

    BLOCK = local-only / mid-operation / unmeasurable work that closing would lose. WARN =
    already-on-disk hygiene. An *unknown* (unmeasurable) unpushed count BLOCKS - an un-measured
    thing is not 'safe', it is unknown (measurement honesty)."""
    blockers, warnings = [], []

    if uncommitted:
        blockers.append(f"{len(uncommitted)} uncommitted change(s) in the working tree")

    up = current["unpushed"]
    if up is None:
        blockers.append("unpushed commits: unknown - could not compare against the remote; verify manually")
    elif up:
        blockers.append(f"{up} commit(s) {current['note']}")

    if in_progress:
        blockers.append(f"a {in_progress} is in progress - finish it (--continue) or abort it "
                        "(--abort) before closing; do NOT plain-commit")

    if stash:
        warnings.append(f"{stash} stash entr{'y' if stash == 1 else 'ies'} - local-only; "
                        "run `git stash list` to review (apply/pop or they sit forgotten)")
    if open_prs:
        warnings.append(f"{len(open_prs)} open PR(s) - already on the server "
                        "(run automerge_status.py to check they merge)")
    if branches["base_missing"]:
        warnings.append("stale branches: unknown - no origin/main ref (run git fetch)")
    else:
        if branches["real_work"]:
            warnings.append(f"{len(branches['real_work'])} local branch(es) with work not in main "
                            "- review before deleting")
        junk = branches["deletable_safe"] + branches["deletable_squash"]
        if junk:
            warnings.append(f"{len(junk)} stale local branch(es) safe to delete")

    return {"safe": not blockers, "blockers": blockers, "warnings": warnings}


# ----------------------------------------------------------------------------------------------
# I/O gather helpers (isolated so tests stub them; each fails soft to a sentinel, never crashes).
# ----------------------------------------------------------------------------------------------
def gather_uncommitted() -> list[str]:
    try:
        return [ln for ln in _git(["status", "--porcelain"]).splitlines() if ln.strip()]
    except subprocess.CalledProcessError:
        return []


def gather_current() -> dict:
    """Current branch, detached state, and commits not on the relevant remote ref.

    Picks the honest comparison base: the upstream if set; else origin/<branch> if the branch was
    pushed without -u; else origin/main (never-pushed) - and labels the count by what it measured,
    so it never claims 'never pushed' about work that is on the server."""
    try:
        branch = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    except subprocess.CalledProcessError:
        branch = "HEAD"
    detached = branch == "HEAD"

    upstream = None
    try:
        upstream = _git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    except subprocess.CalledProcessError:
        upstream = None

    if upstream:
        base, note = upstream, f"not pushed to upstream {upstream}"
    elif not detached and _ref_exists(f"origin/{branch}"):
        base, note = f"origin/{branch}", f"not on origin/{branch} (no upstream set)"
    elif detached:
        base, note = "origin/main", "on a detached HEAD - reflog-only; create a branch before closing"
    else:
        base, note = "origin/main", "never pushed (no remote branch) - live only in this tree"

    return {"branch": branch, "detached": detached, "unpushed": _count(f"{base}..HEAD"), "note": note}


def gather_stash() -> int:
    try:
        return len([ln for ln in _git(["stash", "list"]).splitlines() if ln.strip()])
    except subprocess.CalledProcessError:
        return 0


def gather_in_progress():
    """Name of an in-progress operation (rebase/merge/cherry-pick/revert), or None. A paused rebase
    can leave a CLEAN tree, so `git status` alone would falsely read SAFE."""
    for marker, name in _IN_PROGRESS:
        try:
            path = _git(["rev-parse", "--git-path", marker])
        except subprocess.CalledProcessError:
            continue
        if path and os.path.exists(path):
            return name
    return None


def _is_contained(branch: str) -> bool:
    """True if every patch on `branch` is already present upstream (origin/main), per `git cherry`
    (patch-id equivalence - this is what detects a squash/rebase merge). Fails SAFE to False (->
    real_work / review) when it can't be determined."""
    try:
        out = _git(["cherry", "origin/main", branch])
    except subprocess.CalledProcessError:
        return False
    lines = [ln for ln in out.splitlines() if ln.strip()]
    return all(ln.startswith("-") for ln in lines)  # '+' = a patch not upstream; empty -> contained


def gather_branches() -> dict:
    """Local merged / no-merged branches and the subset whose changes are provably in main.
    Degrades to base_missing=True (not a crash) when origin/main does not exist."""
    try:
        current = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    except subprocess.CalledProcessError:
        current = "HEAD"
    if not _ref_exists("origin/main"):
        return {"merged": [], "no_merged": [], "contained": set(), "base_missing": True}

    skip = {current, "main"}

    def _locals(flag: str) -> list[str]:
        try:
            lines = _git(["branch", flag, "origin/main"]).splitlines()
        except subprocess.CalledProcessError:
            return []
        names = []
        for ln in lines:
            n = _strip_branch(ln)
            if n and n not in skip and not _is_pseudo(n):
                names.append(n)
        return names

    merged = _locals("--merged")
    no_merged = _locals("--no-merged")
    contained = {b for b in no_merged if _is_contained(b)}
    return {"merged": merged, "no_merged": no_merged, "contained": contained, "base_missing": False}


def gather_open_prs():
    """Open PRs via gh (titles sanitised), or None if gh is unavailable/errors/returns a bad shape."""
    try:
        out = subprocess.check_output(
            ["gh", "pr", "list", "--state", "open", "--json", "number,title,url,headRefName,autoMergeRequest"],
            encoding="utf-8", errors="replace", stderr=subprocess.DEVNULL,
        )
        data = json.loads(out)
    except (FileNotFoundError, subprocess.CalledProcessError, json.JSONDecodeError):
        return None
    if not isinstance(data, list):
        return None
    return [p for p in data if isinstance(p, dict)]


def gather_worktrees() -> int:
    """How many git worktrees share this .git. >1 means separate working trees exist - their files
    are isolated but `.git/refs` and `.git/config` are still SHARED. Fails soft to 1."""
    try:
        lines = _git(["worktree", "list", "--porcelain"]).splitlines()
        return max(1, sum(1 for ln in lines if ln.startswith("worktree ")))
    except subprocess.CalledProcessError:
        return 1


# ----------------------------------------------------------------------------------------------
# Reporting
# ----------------------------------------------------------------------------------------------
def _delete_lines(flag: str, names: list[str]) -> list[str]:
    """A runnable `git branch <flag>` line for safely-named branches, plus a manual line for any
    branch whose name carries spaces/shell metachars (which must NOT be pasted into a command)."""
    safe = [n for n in names if _SAFE_BRANCH.match(n)]
    odd = [n for n in names if not _SAFE_BRANCH.match(n)]
    out = []
    if safe:
        out.append(f"       git branch {flag} {' '.join(safe)}")
    if odd:
        out.append(f"       (unusual name - delete by hand, do NOT paste): {', '.join(odd)}")
    return out


def _format_report(state: dict) -> str:
    verdict = state["verdict"]
    cur, branches, prs = state["current"], state["branches"], state["open_prs"]
    out: list[str] = ["Session close-out audit (read-only to your work; nothing was committed/deleted)", ""]

    n = len(state["uncommitted"])
    out.append(f"1. Uncommitted changes : {n if n else 'none'}")
    if n:
        out.append("     -> commit them, or `git stash` (note: a stash is itself local-only - see #3).")

    label = f"on '{cur['branch']}'" + (" (DETACHED HEAD)" if cur["detached"] else "")
    up = cur["unpushed"]
    shown = "unknown" if up is None else up
    out.append(f"2. Unpushed commits    : {shown} {label}")
    if up is None:
        out.append("     -> could not compare against the remote; verify manually before closing.")
    elif up:
        out.append(f"     -> {cur['note']}.")

    out.append(f"3. Stash entries       : {state['stash'] if state['stash'] else 'none'}")
    if state["stash"]:
        out.append("     -> `git stash list`; apply/pop what you need - a stash is local-only.")

    out.append(f"4. In-progress op      : {state['in_progress'] or 'none'}")
    if state["in_progress"]:
        out.append(f"     -> finish (git {state['in_progress']} --continue) or abort (--abort) before closing.")

    if prs is None:
        out.append("5. Open PRs            : unknown (the `gh` CLI is unavailable)")
    else:
        out.append(f"5. Open PRs            : {len(prs) if prs else 'none'}")
        for p in prs or []:
            title = _CTRL.sub(" ", str(p.get("title", "")))[:120]
            auto = "auto-merge ON" if p.get("autoMergeRequest") else "auto-merge OFF"
            out.append(f"     #{p.get('number')} {title}  [{auto}]")

    if branches["base_missing"]:
        out.append("6. Stale local branches: unknown (no origin/main ref - run `git fetch`)")
    else:
        safe, squash, real = branches["deletable_safe"], branches["deletable_squash"], branches["real_work"]
        out.append(f"6. Stale local branches: {len(safe) + len(squash)} deletable, {len(real)} need review")
        if safe:
            out.append(f"     merged into main (delete with -d): {' '.join(safe)}")
            out.extend(_delete_lines("-d", safe))
        if squash:
            out.append(f"     changes already in main, squash/rebase (delete with -D; verified via git cherry): {' '.join(squash)}")
            out.extend(_delete_lines("-D", squash))
        if real:
            out.append(f"     work NOT provably in main - review before deleting: {' '.join(real)}")

    out.append("")
    if verdict["safe"]:
        out.append("VERDICT: SAFE TO CLOSE - nothing local-only or mid-operation would be lost.")
    else:
        out.append("VERDICT: NOT SAFE TO CLOSE YET - these would be lost or left mid-operation on close:")
        for b in verdict["blockers"]:
            out.append(f"  - {b}")
    for w in verdict["warnings"]:
        out.append(f"  (cleanup) {w}")
    out.append("  (scope) Git safety only - this does NOT check whether your TASK is done; "
               "unfinished work -> awb-handover.")

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
    """Gather + classify the whole repo state into one dict. Never raises (every gather fails soft)."""
    raw = gather_branches()
    branches = classify_branches(raw["merged"], raw["no_merged"], raw["contained"])
    branches["base_missing"] = raw["base_missing"]
    uncommitted = gather_uncommitted()
    current = gather_current()
    stash = gather_stash()
    in_progress = gather_in_progress()
    open_prs = gather_open_prs()
    verdict = build_verdict(uncommitted, current, stash, in_progress, open_prs or [], branches)
    return {
        "uncommitted": uncommitted,
        "current": current,
        "stash": stash,
        "in_progress": in_progress,
        "branches": branches,
        "open_prs": open_prs,
        "worktrees": gather_worktrees(),
        "verdict": verdict,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--exit-code", action="store_true",
                        help="exit 1 if anything would be LOST or left mid-operation on close")
    parser.add_argument("--no-fetch", action="store_true",
                        help="skip the `git fetch --prune` refresh (offline; stale remote-tracking refs)")
    args = parser.parse_args(argv)

    try:
        _git(["rev-parse", "--git-dir"])
    except (FileNotFoundError, subprocess.CalledProcessError):
        sys.stderr.write("session_close_audit: not a git repository (or git is not installed).\n")
        return 2

    if not args.no_fetch:
        try:
            subprocess.run(["git", "fetch", "--prune", "--quiet"], check=False, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            pass

    state = audit()
    print(_format_report(state))
    return 1 if (args.exit_code and not state["verdict"]["safe"]) else 0


if __name__ == "__main__":
    sys.exit(main())
