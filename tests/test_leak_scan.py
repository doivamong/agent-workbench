import shutil
import subprocess

import pytest

import leak_scan

requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


def _git(tmp_path, *args):
    subprocess.run(["git", *args], cwd=tmp_path, capture_output=True, text=True, check=True)


def test_detects_private_key(tmp_path):
    f = tmp_path / "x.py"
    f.write_text("k = '''-----BEGIN PRIVATE KEY-----'''\n", encoding="utf-8")  # leak-scan: ignore[private_key_block]
    assert leak_scan.scan_file(f, leak_scan.GENERIC_PATTERNS)


def test_detects_password_assignment(tmp_path):
    f = tmp_path / "x.py"
    f.write_text('password = "hunter2hunter2"\n', encoding="utf-8")  # leak-scan: ignore
    assert leak_scan.scan_file(f, leak_scan.GENERIC_PATTERNS)


def test_ignore_marker_suppresses(tmp_path):
    f = tmp_path / "x.py"
    f.write_text('password = "hunter2hunter2"  # leak-scan: ignore\n', encoding="utf-8")
    assert leak_scan.scan_file(f, leak_scan.GENERIC_PATTERNS) == []


# Split so this test's own source line is not itself flagged by a --entropy self-scan.
_AWS_KEY = "AKIA" + "IOSFODNN7EXAMPLE"


def test_bare_ignore_cannot_hide_hard_secret(tmp_path):
    """A bare `leak-scan: ignore` must NOT silence a real AWS key."""
    f = tmp_path / "x.py"
    f.write_text(f'aws = "{_AWS_KEY}"  # leak-scan: ignore\n', encoding="utf-8")
    found = leak_scan.scan_file(f, leak_scan.GENERIC_PATTERNS)
    assert any(name == "aws_access_key" for _, name, _ in found)


def test_scoped_ignore_silences_named_hard_secret(tmp_path):
    """A named opt-out is the only way to silence a hard secret (intentional fixtures)."""
    f = tmp_path / "x.py"
    f.write_text(f'aws = "{_AWS_KEY}"  # leak-scan: ignore[aws_access_key]\n', encoding="utf-8")
    assert leak_scan.scan_file(f, leak_scan.GENERIC_PATTERNS) == []


def test_example_email_allowed(tmp_path):
    f = tmp_path / "x.py"
    f.write_text("contact = 'dev@example.com'\n", encoding="utf-8")
    assert leak_scan.scan_file(f, leak_scan.GENERIC_PATTERNS) == []


# --- multi-line (cross-line) secret assignment ------------------------------

def test_multiline_catches_cross_line_assignment(tmp_path):
    f = tmp_path / "x.py"
    # value on a later line than the keyword: the per-line scan cannot see this
    f.write_text('api_key = (\n    "abcd1234efgh"\n)\n', encoding="utf-8")  # leak-scan: ignore
    assert leak_scan.scan_file(f, leak_scan.GENERIC_PATTERNS, multiline=False) == []
    found = leak_scan.scan_file(f, leak_scan.GENERIC_PATTERNS, multiline=True)
    assert any(name == "multiline_secret_assign" for _, name, _ in found)


def test_multiline_is_off_by_default(tmp_path):
    f = tmp_path / "x.py"
    f.write_text('password =\n  "supersecret99"\n', encoding="utf-8")  # leak-scan: ignore
    assert leak_scan.scan_file(f, leak_scan.GENERIC_PATTERNS) == []  # opt-in only


def test_multiline_respects_ignore_within_span(tmp_path):
    f = tmp_path / "x.py"
    # opt-out on the value line (any line the assignment spans suppresses it)
    f.write_text('password = (\n  "supersecret99"  # leak-scan: ignore\n)\n', encoding="utf-8")
    assert leak_scan.scan_file(f, leak_scan.GENERIC_PATTERNS, multiline=True) == []


def test_multiline_ignores_keyword_inside_a_string(tmp_path):
    # regression: a keyword *inside* a prompt string must not swallow a later quote
    f = tmp_path / "x.py"
    f.write_text('pw = getpass("Master password: ")\nx = input("type here please")\n', encoding="utf-8")  # leak-scan: ignore (fixture string, not a secret)
    assert leak_scan.scan_file(f, leak_scan.GENERIC_PATTERNS, multiline=True) == []


def test_real_looking_email_flagged(tmp_path):
    f = tmp_path / "x.py"
    f.write_text("contact = 'jane.doe@acme-corp.io'\n", encoding="utf-8")  # leak-scan: ignore
    assert leak_scan.scan_file(f, leak_scan.GENERIC_PATTERNS)


def test_denylist_term(tmp_path):
    f = tmp_path / "x.py"
    f.write_text("# references InternalProjectX\n", encoding="utf-8")
    deny = tmp_path / "deny.txt"
    deny.write_text("InternalProjectX\n", encoding="utf-8")
    patterns = leak_scan.GENERIC_PATTERNS + leak_scan.load_denylist(deny)
    assert leak_scan.scan_file(f, patterns)


def test_redaction_hides_value(tmp_path):
    f = tmp_path / "x.py"
    f.write_text("access_token = 'super_secret_value_123'\n", encoding="utf-8")  # leak-scan: ignore
    findings = leak_scan.scan_file(f, leak_scan.GENERIC_PATTERNS)
    assert findings
    # The full secret must never appear verbatim in the finding output.
    assert "super_secret_value_123" not in findings[0][2]


# --- entropy detection (opt-in) ---------------------------------------------
# The token literal lives in the *test source* with a `# leak-scan: ignore`
# comment so a `--entropy` self-scan won't flag this file; the tmp file written
# below has no such marker, so the scanner still detects it there.
_HIGH_ENTROPY = "aZ3kP9xQ2mW7vR5tY8nB4cF6hJ1lD0sG"  # leak-scan: ignore


def test_entropy_off_by_default(tmp_path):
    f = tmp_path / "x.py"
    f.write_text(f'k = "{_HIGH_ENTROPY}"\n', encoding="utf-8")
    # No keyword and entropy disabled -> nothing flagged.
    assert leak_scan.scan_file(f, leak_scan.GENERIC_PATTERNS) == []


def test_entropy_flags_high_entropy_token(tmp_path):
    f = tmp_path / "x.py"
    f.write_text(f'k = "{_HIGH_ENTROPY}"\n', encoding="utf-8")
    found = leak_scan.scan_file(f, leak_scan.GENERIC_PATTERNS, entropy=True)
    assert any(name == "high_entropy_base64" for _, name, _ in found)


def test_entropy_ignores_prose(tmp_path):
    f = tmp_path / "x.py"
    f.write_text("# the quick brown fox jumps over the lazy dog again today\n", encoding="utf-8")
    assert leak_scan.scan_file(f, leak_scan.GENERIC_PATTERNS, entropy=True) == []


def test_entropy_ignores_short_sha(tmp_path):
    f = tmp_path / "x.py"
    f.write_text("# see commit 6e69b60 and d656ead for details\n", encoding="utf-8")
    assert leak_scan.scan_file(f, leak_scan.GENERIC_PATTERNS, entropy=True) == []


# --- fail-closed denylist (--require-denylist), for private->public port runs ---

def test_require_denylist_errors_when_file_missing(tmp_path):
    rc = leak_scan.main([str(tmp_path), "--denylist", str(tmp_path / "nope.txt"), "--require-denylist"])
    assert rc == 2


def test_require_denylist_errors_on_empty_denylist(tmp_path):
    dl = tmp_path / "deny.txt"
    dl.write_text("# only comments, no effective patterns\n", encoding="utf-8")
    rc = leak_scan.main([str(tmp_path), "--denylist", str(dl), "--require-denylist"])
    assert rc == 2


def test_require_denylist_passes_with_terms(tmp_path):
    dl = tmp_path / "deny.txt"
    dl.write_text("SomeInternalProjectName\n", encoding="utf-8")
    target = tmp_path / "clean.py"
    target.write_text("x = 1\n", encoding="utf-8")
    rc = leak_scan.main([str(target), "--denylist", str(dl), "--require-denylist", "--fail-on-find"])
    assert rc == 0


# --- --respect-gitignore: skip files git won't publish -----------------------

@requires_git
def test_respect_gitignore_drops_ignored_file(tmp_path):
    _git(tmp_path, "init")
    (tmp_path / ".gitignore").write_text("notes/\n", encoding="utf-8")
    (tmp_path / "notes").mkdir()
    # A leak that lives ONLY in a git-ignored file is a false positive: it never ships.
    (tmp_path / "notes" / "scratch.md").write_text("path C:\\Users\\someone\\x\n", encoding="utf-8")
    files = list(leak_scan.iter_text_files(tmp_path))
    assert any(f.name == "scratch.md" for f in files)  # the walker still sees it
    kept, warning = leak_scan.filter_gitignored(tmp_path, files)
    assert warning is None
    assert not any(f.name == "scratch.md" for f in kept)  # but the filter drops it


@requires_git
def test_respect_gitignore_keeps_tracked_and_unignored(tmp_path):
    _git(tmp_path, "init")
    (tmp_path / ".gitignore").write_text("notes/\n", encoding="utf-8")
    (tmp_path / "keep.py").write_text("x = 1\n", encoding="utf-8")
    files = list(leak_scan.iter_text_files(tmp_path))
    kept, warning = leak_scan.filter_gitignored(tmp_path, files)
    assert warning is None
    assert any(f.name == "keep.py" for f in kept)


@requires_git
def test_respect_gitignore_end_to_end_no_false_fail(tmp_path):
    _git(tmp_path, "init")
    (tmp_path / ".gitignore").write_text("private/\n", encoding="utf-8")
    (tmp_path / "private").mkdir()
    (tmp_path / "private" / "leak.md").write_text("home /home/realuser/secret\n", encoding="utf-8")  # leak-scan: ignore, inv: ignore (fixture path, not a real leak)
    # Without the flag the ignored file trips the gate; with it, the gate passes.
    assert leak_scan.main([str(tmp_path), "--fail-on-find"]) == 1
    assert leak_scan.main([str(tmp_path), "--fail-on-find", "--respect-gitignore"]) == 0


def test_filter_gitignored_fails_open_outside_work_tree(tmp_path):
    # Not a git repo -> cannot determine ignores -> scan everything, with a warning.
    f = tmp_path / "x.py"
    f.write_text("x = 1\n", encoding="utf-8")
    kept, warning = leak_scan.filter_gitignored(tmp_path, [f])
    if shutil.which("git") is None:
        assert "git not found" in warning
    else:
        assert warning is not None and "no effect" in warning
    assert kept == [f]  # fail open: nothing dropped


# --- modern token shapes (sk-/gh*/AIza/glpat-/JWT/Bearer) --------------------
# Tokens are assembled at runtime from split parts so this test's own source is not
# flagged by the --entropy self-scan that CI/pre-commit run (precedent: _AWS_KEY above).
_NEW_TOKENS = {
    "ai_provider_key": "sk-" + "ant-" + "A" * 40,
    "github_token": "ghp_" + "B" * 36,
    "github_pat": "github_" + "pat_" + "C" * 30,
    "google_api_key": "AIza" + "D" * 35,
    "gitlab_pat": "glpat-" + "E" * 24,
    "jwt": "eyJ" + "a" * 12 + "." + "b" * 12 + "." + "c" * 12,
    "bearer_token": "Bearer " + "F" * 30,
}


@pytest.mark.parametrize("name,token", list(_NEW_TOKENS.items()))
def test_modern_token_shape_is_detected(tmp_path, name, token):
    f = tmp_path / "x.py"
    f.write_text(f'v = "{token}"\n', encoding="utf-8")
    found = leak_scan.scan_file(f, leak_scan.GENERIC_PATTERNS)
    assert any(n == name for _, n, _ in found), f"{name} not detected in {token!r}"


@pytest.mark.parametrize("name", ["github_token", "github_pat", "google_api_key"])
def test_new_hard_token_not_silenced_by_bare_ignore(tmp_path, name):
    """The hyphen-free credential shapes are HARD: a bare opt-out must not hide them."""
    f = tmp_path / "x.py"
    f.write_text(f'v = "{_NEW_TOKENS[name]}"  # leak-scan: ignore\n', encoding="utf-8")
    assert any(n == name for _, n, _ in leak_scan.scan_file(f, leak_scan.GENERIC_PATTERNS))


@pytest.mark.parametrize("name", ["ai_provider_key", "gitlab_pat"])
def test_hyphen_bodied_token_is_soft_and_bare_ignore_silences_it(tmp_path, name):
    """sk-/glpat- bodies can still collide with an unusual kebab identifier, so they are SOFT: a
    bare opt-out clears a rare false positive without needing a named one."""
    f = tmp_path / "x.py"
    f.write_text(f'v = "{_NEW_TOKENS[name]}"  # leak-scan: ignore\n', encoding="utf-8")
    assert leak_scan.scan_file(f, leak_scan.GENERIC_PATTERNS) == []


def test_new_hard_token_silenced_by_named_ignore(tmp_path):
    f = tmp_path / "x.py"
    f.write_text(f'v = "{_NEW_TOKENS["github_token"]}"  # leak-scan: ignore[github_token]\n',
                 encoding="utf-8")
    assert leak_scan.scan_file(f, leak_scan.GENERIC_PATTERNS) == []


def test_jwt_is_soft_and_bare_ignore_silences_it(tmp_path):
    """JWTs appear in docs/examples, so jwt is SOFT - a bare opt-out silences it."""
    f = tmp_path / "x.py"
    f.write_text(f'token = "{_NEW_TOKENS["jwt"]}"  # leak-scan: ignore\n', encoding="utf-8")
    assert leak_scan.scan_file(f, leak_scan.GENERIC_PATTERNS) == []


@pytest.mark.parametrize("prose", [
    "send a Bearer token in the Authorization header",  # 'token' is short -> below the bound
    "use risk-assessment and a sklearn model",          # 'sk-' inside a word, no boundary
    "the AIza prefix marks a Google key",               # 'AIza' without the 35-char body
    "a sk-fading-circle-spinner-bounce CSS spinner class from SpinKit",  # all-lowercase kebab -> no [A-Z0-9] floor
    "the glpat-this-is-a-long-placeholder-value config slug",           # all-lowercase kebab after glpat-
])
def test_modern_shapes_do_not_false_positive_on_prose(tmp_path, prose):
    f = tmp_path / "x.py"
    f.write_text(prose + "\n", encoding="utf-8")
    found = leak_scan.scan_file(f, leak_scan.GENERIC_PATTERNS)
    assert not any(n in {"bearer_token", "ai_provider_key", "google_api_key", "gitlab_pat"}
                   for _, n, _ in found), f"false positive on prose: {found}"


# --- fail CLOSED on an unreadable in-scope file ------------------------------
# A leak scanner that silently skips a file it can't read can green-light a leak. The old
# code did `except OSError: return []`; these prove it now surfaces an unreadable_file finding.

def test_unreadable_file_surfaces_finding(tmp_path):
    """scan_file must not silently return [] when a path can't be read. Passing a directory
    triggers the OSError read path portably (PermissionError on Windows, IsADirectoryError on
    POSIX — both OSError subclasses)."""
    d = tmp_path / "subdir"
    d.mkdir()
    found = leak_scan.scan_file(d, leak_scan.GENERIC_PATTERNS)
    assert any(name == "unreadable_file" for _, name, _ in found)


def test_unreadable_file_fails_closed_under_fail_on_find(tmp_path, monkeypatch):
    """End-to-end: an unreadable in-scope file makes --fail-on-find exit non-zero instead of
    greening the scan. The old `return []` fail-open exited 0 — this bites that."""
    target = tmp_path / "secret.py"
    target.write_text("x = 1\n", encoding="utf-8")
    real_read_text = leak_scan.Path.read_text

    def boom(self, *a, **k):
        if self.name == "secret.py":
            raise PermissionError("locked")
        return real_read_text(self, *a, **k)

    monkeypatch.setattr(leak_scan.Path, "read_text", boom)
    assert leak_scan.main([str(tmp_path), "--fail-on-find"]) == 1
