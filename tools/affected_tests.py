#!/usr/bin/env python3
"""Affected Tests selector.

Given a list of changed files, returns the test files that need to run via a
reverse import graph built with Python's ``ast`` module.  Goal: reduce CI /
local test time by running only the tests that are actually impacted.

Pattern inspired by colbymchenry/codegraph ``codegraph affected`` (MIT,
© 2026 Colby McHenry). Re-implemented in Python with stdlib ``ast`` —
no code was copied.  Key adaptation: ``ast.walk()`` handles lazy imports
inside function bodies (common when a codebase defers imports on purpose).

Usage:
    # From git diff
    python tools/affected_tests.py --diff

    # Pass files directly
    python tools/affected_tests.py src/foo_service.py

    # Pipe from git
    git diff --name-only HEAD | python tools/affected_tests.py --stdin

    # CI hook
    git diff --name-only HEAD | python tools/affected_tests.py --stdin --quiet | xargs pytest

Conservative fallback (full suite) triggers:
    - Core entry-point files change (e.g. main.py, app.py, manage.py)
    - tests/conftest.py changes
    - shared test-helper / build-config changes
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path

# Windows: force UTF-8 output so non-ASCII characters render correctly.
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    if getattr(sys.stdout, "buffer", None) is not None:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if getattr(sys.stderr, "buffer", None) is not None:
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "tools" / ".cache"
CACHE_FILE = CACHE_DIR / "affected_tests.json"

# Directories containing source code to scan for import edges (forward graph).
# These double as module-resolution roots (sys.path-style), so a bare ``import foo``
# resolves to ``<dir>/foo.py`` — matching how conftest.py injects these dirs onto
# sys.path. Tune to your project's layout (e.g. add your package/app dirs here).
SCAN_DIRS = ("src", "lib", "tests", "tools", "scripts")

# Python files whose change triggers the full test suite (high blast radius).
# Add your own "everything depends on this" .py files (app entrypoints, shared
# fixtures) here. Non-.py high-blast files are handled by _is_high_blast_nonpy below
# (build config like a pyproject.toml is caught there as an unknown non-.py → full suite).
FULL_SUITE_TRIGGERS = {
    "conftest.py",
    "tests/conftest.py",
}

# Sentinel value returned when the full suite must run.
RUN_ALL_MARKER = "__RUN_ALL_TESTS__"


def _is_high_blast_nonpy(rel: str) -> bool:
    """A non-.py change a test renders or validates — so it must run the full suite.

    These files carry no Python import edge, so the import graph cannot see their blast
    radius. The selector used to drop every non-.py path before this check, silently
    selecting *zero* tests for a changed template / skill / manifest (the B1 bug).
    """
    if (rel.startswith("ui/") or rel.startswith("ops/")) and rel.endswith((".jinja", ".html")):
        return True  # templates that test_ui_web / admin tests render
    if rel.endswith("/SKILL.md") or rel.endswith("skill-registry.md"):
        return True  # skill definitions / registry — gated by skill-lint + skill-usage tests
    if rel.endswith("manifest.json") or rel.endswith("known_violations.json"):
        return True  # the file-set manifest / invariant baseline the gates check
    if rel.endswith(".claude/settings.json"):
        return True  # the hook control-plane
    return False


def _is_doc_nonpy(rel: str) -> bool:
    """A non-.py documentation change with no test impact (markdown prose).

    SKILL.md / skill-registry.md are .md but high-blast, so they are matched by
    _is_high_blast_nonpy *first*; only plain docs reach here. Anything non-.py that is
    neither high-blast nor a doc is treated as unknown and conservatively runs the full
    suite (fail-safe), never "no tests".
    """
    return rel.endswith(".md")

CACHE_VERSION = 1


def _is_python(path: Path) -> bool:
    return path.suffix == ".py" and path.is_file()


def _rel(path: Path) -> str:
    """Return path relative to ROOT in posix style."""
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _all_python_files() -> list[Path]:
    """Collect all .py files under SCAN_DIRS plus selected top-level files."""
    files: list[Path] = []
    for d in SCAN_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        for p in base.rglob("*.py"):
            if "__pycache__" in p.parts:
                continue
            files.append(p)

    for top in ("main.py", "app.py", "manage.py"):
        p = ROOT / top
        if p.exists():
            files.append(p)

    return files


def _module_to_path(module: str) -> Path | None:
    """Resolve a dotted/bare module name to a source file path.

    Tries the repo root first (package-rooted imports like ``src.foo_service``), then
    each SCAN_DIR as a sys.path-style root. The latter is what makes a flat layout work:
    a bare ``import leak_scan`` (resolved at runtime because conftest injects ``tools/``
    onto sys.path) maps to ``tools/leak_scan.py`` instead of silently resolving to
    nothing — which previously left the import graph empty on this kind of repo.
    """
    parts = module.split(".")
    roots = [ROOT, *(ROOT / d for d in SCAN_DIRS)]
    for base in roots:
        candidate = base.joinpath(*parts).with_suffix(".py")
        if candidate.exists():
            return candidate
        pkg = base.joinpath(*parts) / "__init__.py"
        if pkg.exists():
            return pkg
    return None


def _extract_imports(file_path: Path) -> set[Path]:
    """AST scan: return the set of file paths imported by ``file_path``.

    Handles both top-level imports and lazy imports inside function/method bodies.
    """
    targets: set[Path] = set()
    try:
        source = file_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, OSError):
        return targets

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                resolved = _module_to_path(alias.name)
                if resolved:
                    targets.add(resolved)
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            resolved = _module_to_path(node.module)
            if resolved:
                targets.add(resolved)
            for alias in node.names:
                sub = _module_to_path(f"{node.module}.{alias.name}")
                if sub:
                    targets.add(sub)

    return targets


def _files_hash(files: list[Path]) -> str:
    """Hash file paths + contents — used for cache invalidation.

    Content-based, not mtime-based, on purpose: an mtime-second key could serve a
    STALE graph after two edits within the same wall-clock second (or on filesystems
    with coarse mtime granularity). Hashing content is collision-free for that case
    and also avoids needless rebuilds on a no-op ``touch``.
    """
    h = hashlib.sha256()
    for p in sorted(files, key=lambda x: x.as_posix()):
        try:
            h.update(p.as_posix().encode())
            h.update(b"\0")
            h.update(p.read_bytes())
            h.update(b"\0")
        except OSError:
            continue
    return h.hexdigest()[:16]


def build_import_graph(force: bool = False) -> dict[str, list[str]]:
    """Build the forward import graph.  Returns ``{file: [imported_files]}``.

    The result is cached on disk keyed by a hash of all file mtimes.  The
    cache is automatically invalidated when any source file changes.
    """
    files = _all_python_files()
    current_hash = _files_hash(files)

    if not force and CACHE_FILE.exists():
        try:
            cached = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            if cached.get("version") == CACHE_VERSION and cached.get("files_hash") == current_hash:
                return cached["forward"]
        except (json.JSONDecodeError, KeyError, OSError):
            pass

    forward: dict[str, list[str]] = {}
    for f in files:
        imports = _extract_imports(f)
        forward[_rel(f)] = sorted(_rel(p) for p in imports)

    # Honesty about scope: if no import edges were found, graph-based selection is a
    # no-op and we silently degrade to name-based matching. Warn so the caller knows
    # to tune SCAN_DIRS to their layout rather than trusting an empty graph.
    if files and not any(forward.values()):
        print(
            f"affected_tests: WARNING — no import edges found under SCAN_DIRS {SCAN_DIRS}; "
            "graph-based selection is inactive, falling back to name-based matching only. "
            "Tune SCAN_DIRS in tools/affected_tests.py to your project's layout.",
            file=sys.stderr,
        )

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": CACHE_VERSION,
        "files_hash": current_hash,
        "forward": forward,
    }
    CACHE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return forward


def _reverse_graph(forward: dict[str, list[str]]) -> dict[str, set[str]]:
    """Invert the forward graph: ``{target: {importers}}``."""
    reverse: dict[str, set[str]] = {}
    for importer, targets in forward.items():
        for tgt in targets:
            reverse.setdefault(tgt, set()).add(importer)
    return reverse


def _is_test_file(rel_path: str) -> bool:
    return rel_path.startswith("tests/") and Path(rel_path).name.startswith("test_")


def _direct_test_match(changed_rel: str) -> list[str]:
    """Heuristic: ``src/foo_service.py`` → ``tests/test_foo_service.py`` / ``tests/test_foo_service_*.py``."""
    name = Path(changed_rel).stem
    if not name or name.startswith("_"):
        return []
    matches: list[str] = []
    test_dir = ROOT / "tests"
    for pattern in (f"test_{name}.py", f"test_{name}_*.py"):
        for p in test_dir.glob(pattern):
            matches.append(_rel(p))
    return matches


def affected(changed: list[str], depth: int = 5, force_full: bool = False) -> list[str]:
    """Return the list of test files impacted by ``changed`` (posix relative paths).

    Uses BFS up to ``depth`` hops on the reverse import graph, then adds
    direct name-based matches as a heuristic fallback.
    """
    if force_full:
        return [RUN_ALL_MARKER]

    changed_norm = [c.replace("\\", "/").lstrip("./") for c in changed if c.strip()]

    # Classify non-.py files BEFORE filtering to .py (B1). The old code dropped every
    # non-.py path here, so a high-blast artifact (a template, a SKILL.md, a manifest)
    # selected zero tests. Now: a high-blast non-.py runs the full suite; a doc is a
    # no-op; an unknown non-.py runs the full suite (fail-safe). Only .py files fall
    # through to graph-based selection below.
    py_changed: list[str] = []
    for c in changed_norm:
        if c.endswith(".py"):
            py_changed.append(c)
        elif _is_high_blast_nonpy(c):
            return [RUN_ALL_MARKER]
        elif _is_doc_nonpy(c):
            continue  # documentation: no test impact
        else:
            return [RUN_ALL_MARKER]  # unknown non-.py → conservative full run

    changed_norm = py_changed
    if not changed_norm:
        return []

    for c in changed_norm:
        if c in FULL_SUITE_TRIGGERS:
            return [RUN_ALL_MARKER]

    forward = build_import_graph()
    reverse = _reverse_graph(forward)

    visited: set[str] = set(changed_norm)
    frontier: set[str] = set(changed_norm)
    for _ in range(max(1, depth)):
        next_frontier: set[str] = set()
        for node in frontier:
            for importer in reverse.get(node, set()):
                if importer not in visited:
                    visited.add(importer)
                    next_frontier.add(importer)
        if not next_frontier:
            break
        frontier = next_frontier

    affected_tests: set[str] = {p for p in visited if _is_test_file(p)}

    for c in changed_norm:
        for direct in _direct_test_match(c):
            affected_tests.add(direct)

    return sorted(affected_tests)


def _run_pytest(selected: list[str]) -> int:
    """Run ``pytest -n auto`` on the selected tests; return pytest's exit code.

    RUN_ALL → full suite; empty → skip with exit 0 (nothing impacted); otherwise run only
    the selected files. Used by the pre-commit hook so a doc-only commit skips pytest while
    a code change still runs the tests that cover it. Cross-platform (no shell pipe).
    """
    base = [sys.executable, "-m", "pytest", "-n", "auto", "-q"]
    if RUN_ALL_MARKER in selected:
        cmd = base
    elif not selected:
        print(
            "affected_tests: no impacted tests for the changed files — skipping pytest.",
            file=sys.stderr,
        )
        return 0
    else:
        cmd = base + selected
    return subprocess.call(cmd, cwd=str(ROOT))


def _read_stdin() -> list[str]:
    return [line.strip() for line in sys.stdin if line.strip()]


def _read_git_diff() -> list[str]:
    try:
        out = subprocess.check_output(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=ROOT,
            encoding="utf-8",
            errors="replace",
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("files", nargs="*", help="Changed files (posix relative paths)")
    parser.add_argument("--stdin", action="store_true", help="Read file list from stdin (one file per line)")
    parser.add_argument("--diff", action="store_true", help="Read from `git diff --name-only HEAD`")
    parser.add_argument("--depth", type=int, default=5, help="Max BFS depth (default: 5)")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--quiet", action="store_true", help="Print file paths only (pytest-friendly)")
    parser.add_argument("--force-full", action="store_true", help="Skip analysis, always return full suite")
    parser.add_argument("--rebuild-cache", action="store_true", help="Force rebuild of the import graph cache")
    parser.add_argument("--run", action="store_true",
                        help="Run pytest -n auto on the affected tests (full suite if a high-blast "
                             "file changed; skip with exit 0 if nothing is impacted)")
    args = parser.parse_args()

    if args.rebuild_cache:
        build_import_graph(force=True)
        if not args.quiet:
            print(f"Cache rebuilt: {CACHE_FILE}", file=sys.stderr)
        return 0

    sources: list[str] = list(args.files)
    if args.stdin:
        sources.extend(_read_stdin())
    if args.diff:
        sources.extend(_read_git_diff())

    if not sources:
        if not args.quiet:
            print("No input files. Use --diff, --stdin, or pass files as arguments.", file=sys.stderr)
        return 0

    result = affected(sources, depth=args.depth, force_full=args.force_full)

    if args.run:
        return _run_pytest(result)

    if RUN_ALL_MARKER in result:
        if args.json:
            print(json.dumps({"full_suite": True, "reason": "high_blast_radius_file_changed"}))
        elif args.quiet:
            print("tests/")
        else:
            print("FULL SUITE - high blast radius file changed (entrypoint/conftest/build-config)")
            print("Run: pytest tests/")
        return 0

    if args.json:
        print(json.dumps({"full_suite": False, "tests": result, "count": len(result)}))
    elif args.quiet:
        for t in result:
            print(t)
    else:
        if not result:
            print("No tests affected.")
            return 0
        print(f"Affected tests ({len(result)}):")
        for t in result:
            print(f"  {t}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
