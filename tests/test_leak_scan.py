import leak_scan


def test_detects_private_key(tmp_path):
    f = tmp_path / "x.py"
    f.write_text("k = '''-----BEGIN PRIVATE KEY-----'''\n", encoding="utf-8")  # leak-scan: ignore
    assert leak_scan.scan_file(f, leak_scan.GENERIC_PATTERNS)


def test_detects_password_assignment(tmp_path):
    f = tmp_path / "x.py"
    f.write_text('password = "hunter2hunter2"\n', encoding="utf-8")  # leak-scan: ignore
    assert leak_scan.scan_file(f, leak_scan.GENERIC_PATTERNS)


def test_ignore_marker_suppresses(tmp_path):
    f = tmp_path / "x.py"
    f.write_text('password = "hunter2hunter2"  # leak-scan: ignore\n', encoding="utf-8")
    assert leak_scan.scan_file(f, leak_scan.GENERIC_PATTERNS) == []


def test_example_email_allowed(tmp_path):
    f = tmp_path / "x.py"
    f.write_text("contact = 'dev@example.com'\n", encoding="utf-8")
    assert leak_scan.scan_file(f, leak_scan.GENERIC_PATTERNS) == []


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
