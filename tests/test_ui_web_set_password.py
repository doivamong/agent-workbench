"""Tests for ui/web/set_password.py — the offline CLI that sets/resets the /admin password.

These are stdlib-only (the CLI imports ``passwords``, not Flask), so they collect and run on
every platform — no Flask skipif needed. The cross-check that matters: a hash the CLI writes
must verify with the SAME ``passwords.verify_password`` the web login uses.
"""
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ui" / "web"))
import passwords  # noqa: E402
import set_password as sp  # noqa: E402


def _feed_stdin(monkeypatch, text: str) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(text))


def test_stdin_writes_a_verifiable_hash(tmp_path, monkeypatch):
    _feed_stdin(monkeypatch, "super-secret-pw\n")
    rc = sp.main(["--root", str(tmp_path), "--stdin"])
    assert rc == 0
    store = tmp_path / ".ops" / "admin.hash"
    assert store.is_file()
    stored = store.read_text(encoding="utf-8").strip()
    assert stored.startswith("pbkdf2_sha256$")
    assert "super-secret-pw" not in stored          # plaintext never written
    assert passwords.verify_password("super-secret-pw", stored)
    assert not passwords.verify_password("wrong-pw", stored)


def test_stdin_rejects_too_short_and_writes_nothing(tmp_path, monkeypatch):
    _feed_stdin(monkeypatch, "short\n")             # < MIN_PASSWORD_LEN (8)
    rc = sp.main(["--root", str(tmp_path), "--stdin"])
    assert rc == 2
    assert not (tmp_path / ".ops" / "admin.hash").exists()


def test_overwrites_an_existing_hash(tmp_path, monkeypatch):
    store = tmp_path / ".ops" / "admin.hash"
    store.parent.mkdir(parents=True)
    store.write_text("pbkdf2_sha256$1$00$00", encoding="utf-8")  # a stale/garbage prior hash
    _feed_stdin(monkeypatch, "brand-new-passphrase\n")
    assert sp.main(["--root", str(tmp_path), "--stdin"]) == 0
    new = store.read_text(encoding="utf-8").strip()
    assert passwords.verify_password("brand-new-passphrase", new)


def test_strips_trailing_cr_from_stdin(tmp_path, monkeypatch):
    # A Windows pipe can deliver CRLF; the CR must not become part of the password.
    _feed_stdin(monkeypatch, "windows-line-pw\r\n")
    assert sp.main(["--root", str(tmp_path), "--stdin"]) == 0
    stored = (tmp_path / ".ops" / "admin.hash").read_text(encoding="utf-8").strip()
    assert passwords.verify_password("windows-line-pw", stored)
    assert not passwords.verify_password("windows-line-pw\r", stored)
