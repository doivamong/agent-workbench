import leak_scan


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
