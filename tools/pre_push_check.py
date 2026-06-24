#!/usr/bin/env python3
"""Read-only pre-push integrity check (stdlib): one PASS/FAIL over the 4-point check.

Before a push, four things must hold. This verifies them WITHOUT mutating anything — no commit,
no push, no file write, no git state change (every git call is a read). It exits 0 only if all
four pass, non-zero if any fails, and non-zero on its own internal error too: **fail CLOSED**, a
broken check must refuse the push, never wave it through. It is deliberately NOT wrapped in
hook_logger.hook_main (which exits 0 on an unhandled exception — that would fail OPEN).

The four points (the private-source push policy generalised to this public repo):
  1. remote  — the push target (default `origin`) exists and points at the expected repo.
  2. commits — `git log <base>..HEAD` is a non-empty commit set on a feature branch, not the
               protected branch itself (you push a branch and open a PR, never push main direct).
  3. gate    — the leak scan is clean: the one thing you must never push.
  4. clean   — no outgoing file is gitignored or under a private path (.porting/, handovers/,
               plans/, .ops/) — those must never reach the public repo.

Usage:
    python tools/pre_push_check.py                     # check HEAD vs origin/main
    python tools/pre_push_check.py --base origin/main --remote origin
    python tools/pre_push_check.py --expect-remote-substr agent-workbench
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # Windows: ẩn cửa sổ console; non-Windows: 0 (no-op)

# Outgoing files under these prefixes must never reach the public repo.
_PRIVATE_PREFIXES = (".porting/", "handovers/", "plans/", ".ops/")

# Leak scan flags kept identical to the pre-commit / CI invocation.
_LEAK_FLAGS = ["--entropy", "--fail-on-find", "--respect-gitignore"]


class CheckError(RuntimeError):
    """An internal failure of the checker itself — must fail CLOSED (non-zero)."""


def _git(args: list[str], repo: Path) -> str:
    """Run a read-only git command in ``repo``; raise CheckError on failure (fail closed)."""
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo), *args], encoding="utf-8", stderr=subprocess.STDOUT,
            creationflags=_NO_WINDOW
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise CheckError(f"git {' '.join(args)} failed: {exc}") from exc


def check_remote(repo: Path, remote: str, expect_substr: str | None) -> tuple[bool, str]:
    url = _git(["remote", "get-url", remote], repo)
    if expect_substr and expect_substr not in url:
        return False, f"remote '{remote}' is {url!r}, which does not contain {expect_substr!r}"
    return True, f"remote '{remote}' -> {url}"


def check_commits(repo: Path, base: str) -> tuple[bool, str]:
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], repo)
    if branch == "HEAD":
        return False, "HEAD is detached — push from a named branch"
    if branch == "main":
        return False, "on 'main' — push a feature branch and open a PR, not main directly"
    commits = _git(["log", f"{base}..HEAD", "--oneline"], repo)
    if not commits:
        return False, f"no commits ahead of {base} — nothing to push"
    n = len(commits.splitlines())
    return True, f"{n} commit(s) ahead of {base} on branch '{branch}'"


def _run_leak_scan(repo: Path) -> tuple[int, str]:
    """Run the leak scanner read-only; return (exit_code, output). Isolated for testing."""
    scanner = Path(__file__).resolve().parent / "leak_scan.py"
    proc = subprocess.run(
        [sys.executable, str(scanner), str(repo), *_LEAK_FLAGS],
        capture_output=True, text=True, creationflags=_NO_WINDOW,
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def check_gate(repo: Path) -> tuple[bool, str]:
    code, out = _run_leak_scan(repo)
    if code != 0:
        tail = out.splitlines()[-1] if out else "(no output)"
        return False, f"leak scan FAILED (exit {code}): {tail}"
    return True, "leak scan clean"


def check_outgoing_clean(repo: Path, base: str) -> tuple[bool, str]:
    names = _git(["log", f"{base}..HEAD", "--name-only", "--pretty=format:"], repo)
    files = sorted({f for f in names.splitlines() if f.strip()})
    bad = [f for f in files if f.startswith(_PRIVATE_PREFIXES)]
    # Also catch anything git itself considers ignored that was force-added into a commit.
    for f in files:
        if f in bad:
            continue
        try:
            if subprocess.run(["git", "-C", str(repo), "check-ignore", "-q", f],
                              creationflags=_NO_WINDOW).returncode == 0:
                bad.append(f)
        except FileNotFoundError as exc:
            raise CheckError(f"git check-ignore unavailable: {exc}") from exc
    if bad:
        return False, f"outgoing set includes private/ignored file(s): {', '.join(sorted(bad))}"
    return True, f"no private/ignored files in {len(files)} outgoing file(s)"


def run_checks(repo: Path, remote: str, base: str, expect_substr: str | None) -> list[tuple[str, bool, str]]:
    return [
        ("remote", *check_remote(repo, remote, expect_substr)),
        ("commits", *check_commits(repo, base)),
        ("gate", *check_gate(repo)),
        ("clean", *check_outgoing_clean(repo, base)),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default=".", help="repository root (default: cwd)")
    parser.add_argument("--remote", default="origin", help="expected push remote (default: origin)")
    parser.add_argument("--base", default="origin/main", help="base ref for the outgoing set (default: origin/main)")
    parser.add_argument("--expect-remote-substr", default=None,
                        help="fail unless the remote URL contains this substring")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    try:
        results = run_checks(repo, args.remote, args.base, args.expect_remote_substr)
    except CheckError as exc:
        sys.stderr.write(f"pre_push_check: internal error, refusing the push (fail closed): {exc}\n")
        return 2

    all_ok = True
    for name, ok, detail in results:
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {name}: {detail}")
        all_ok = all_ok and ok

    if all_ok:
        print("\npre-push check PASSED (4/4). Safe to push.")
        return 0
    print("\npre-push check FAILED — do not push until the FAIL line(s) above are resolved.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
