#!/usr/bin/env python3
"""ui/web/set_password.py — set or change the /admin password from the command line.

Offline counterpart to the web change-password form: it writes the same pbkdf2 hash to
``<root>/.ops/admin.hash`` (gitignored, never committed). Use it to BOOTSTRAP the first
password, or to RECOVER when you've forgotten it — running on the host machine is what
proves you're the owner, so unlike the web form it does NOT ask for the old password.

stdlib-only (imports ``passwords``, not Flask) on purpose: it must work even when the web
stack / venv is broken. The plaintext is never written — only the salted hash.

Usage (double-click ops/win/set_password.bat, or):
    python ui/web/set_password.py                 # prompt twice, hidden input
    python ui/web/set_password.py --root D:/proj  # target another checkout
    echo my-new-pass | python ui/web/set_password.py --stdin   # non-interactive / scripted

HONEST LIMIT: this only sets the *stored* hash. If ``AWB_ADMIN_PASSWORD`` is also set in the
environment, the stored hash takes precedence; remove the env var if you want to be sure
which one is in effect. Restarting the dashboard is not required — the hash is read per request.
"""
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import passwords  # noqa: E402  — shared stdlib hashing (same format as the web form)

# The success/error copy is Vietnamese with diacritics + a ✓; on Windows a redirected stdout
# defaults to cp1252 and would UnicodeEncodeError mid-print (writing the file first, then
# crashing with a misleading exit 1). Force UTF-8, guarding each stream (it may be None under
# pythonw, or a StringIO under test, where reconfigure is absent).
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None:
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

REPO_ROOT = HERE.parent.parent


def _store_path(root: Path) -> Path:
    return root / ".ops" / "admin.hash"


def _read_new_password(use_stdin: bool) -> str:
    """Return a validated new password, or raise SystemExit with a clear message.

    --stdin reads a single line (scripted/tested use); otherwise prompt twice with hidden
    input and require the two entries to match. Length is enforced in both paths."""
    if use_stdin:
        pw = sys.stdin.readline().rstrip("\n").rstrip("\r")
        if len(pw) < passwords.MIN_PASSWORD_LEN:
            raise SystemExit(f"error: password must be at least {passwords.MIN_PASSWORD_LEN} characters")
        return pw
    while True:
        pw = getpass.getpass("Mật khẩu admin mới: ")
        if len(pw) < passwords.MIN_PASSWORD_LEN:
            print(f"  ! Tối thiểu {passwords.MIN_PASSWORD_LEN} ký tự — thử lại.", file=sys.stderr)
            continue
        again = getpass.getpass("Nhập lại để xác nhận: ")
        if pw != again:
            print("  ! Hai lần nhập không khớp — thử lại.", file=sys.stderr)
            continue
        return pw


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Set/reset the /admin password (writes .ops/admin.hash).")
    ap.add_argument("--root", default=str(REPO_ROOT),
                    help="Repo/checkout whose .ops/admin.hash to write (default: this repo).")
    ap.add_argument("--stdin", action="store_true",
                    help="Read the password from one line of stdin instead of prompting.")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    try:
        pw = _read_new_password(args.stdin)
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (KeyboardInterrupt, EOFError):
        print("\nĐã huỷ — chưa đổi mật khẩu.", file=sys.stderr)
        return 130

    store = _store_path(root)
    try:
        store.parent.mkdir(parents=True, exist_ok=True)
        store.write_text(passwords.hash_password(pw), encoding="utf-8")
    except OSError as exc:
        print(f"error: could not write {store}: {exc}", file=sys.stderr)
        return 1

    print(f"✓ Đã đặt mật khẩu admin. Hash lưu tại: {store}")
    print("  Đăng nhập tại /admin/login bằng mật khẩu mới (không cần khởi động lại).")
    print("  Lưu ý: nếu có biến môi trường AWB_ADMIN_PASSWORD, hash đã lưu này được ưu tiên.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
