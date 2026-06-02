#!/usr/bin/env python3
"""Runnable demo for scripts/secrets_guard.py.

Two parts, both stdlib only:
  1. The byte-level crypto API: an encrypt -> decrypt round-trip, and that a wrong
     password or any tampering is rejected (the HMAC integrity tag fails).
  2. The file/CLI workflow you actually run day to day: `status` -> `encrypt` ->
     `status` -> `decrypt`, including the stale-detection that lets a pre-commit
     hook block a commit when a plaintext file has drifted ahead of its .enc.

    python examples/secrets_demo.py
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import secrets_guard  # noqa: E402
from secrets_guard import decrypt_bytes, encrypt_bytes  # noqa: E402

PASSPHRASE = "correct horse battery staple"  # leak-scan: ignore (demo passphrase)


def demo_byte_api() -> int:
    """Part 1 - the cryptographic primitive (encrypt_bytes / decrypt_bytes)."""
    print("=== Part 1: byte-level crypto API ===")
    secret = b'{"api_key": "live_do_not_log_this", "db_password": "s3cr3t"}'

    print("Plaintext :", secret.decode())

    blob = encrypt_bytes(secret, PASSPHRASE)
    print(f"Encrypted : {len(blob)} bytes (magic+version + salt + HMAC tag + ciphertext; nonce derived from salt)")

    back = decrypt_bytes(blob, PASSPHRASE)
    assert back == secret, "round-trip failed!"
    print("Decrypted :", back.decode(), "  <- round-trip OK")

    # Wrong password is rejected.
    try:
        decrypt_bytes(blob, "wrong password")
        print("ERROR: wrong password should have failed")
        return 1
    except ValueError as e:
        print(f"Wrong pw  : rejected ({e})")

    # Tampering is detected (flip one ciphertext byte).
    tampered = bytearray(blob)
    tampered[-1] ^= 0x01
    try:
        decrypt_bytes(bytes(tampered), PASSPHRASE)
        print("ERROR: tampered data should have failed")
        return 1
    except ValueError as e:
        print(f"Tampered  : rejected ({e})")
    return 0


def demo_file_workflow() -> int:
    """Part 2 - the CLI workflow (status / encrypt / decrypt) on real files.

    secrets_guard operates on the (plaintext_path, encrypted_path) pairs in its
    module-global TARGETS. We repoint TARGETS at a throwaway temp dir so the demo
    is self-contained and never touches your real project files; TARGETS and the
    env var are restored in the finally block.
    """
    print("\n=== Part 2: file/CLI workflow (status -> encrypt -> decrypt) ===")
    tmp = Path(tempfile.mkdtemp(prefix="secrets_demo_"))
    plain = tmp / "config.json"
    enc = tmp / "config.json.enc"
    plain.write_text('{"api_key": "live_do_not_log_this"}', encoding="utf-8")

    saved_targets = secrets_guard.TARGETS
    # cmd_encrypt/cmd_decrypt take the password as an argument; the env var only
    # matters if you call the CLI via _get_password. Set it so the demo is fully
    # non-interactive either way.
    os.environ["SECRETS_GUARD_PASSWORD"] = PASSPHRASE  # leak-scan: ignore (demo passphrase)
    try:
        secrets_guard.TARGETS = [(str(plain), str(enc))]

        print("\n[1] status before encrypt (expect: PLAINTEXT only -> stale):")
        rc = secrets_guard.cmd_status()
        print(f"    exit code = {rc}  (non-zero lets a pre-commit hook block the commit)")

        print("\n[2] encrypt (only the .enc should ever be committed):")
        secrets_guard.cmd_encrypt(PASSPHRASE)

        print("\n[3] status after encrypt (expect: OK / up-to-date):")
        rc = secrets_guard.cmd_status()
        print(f"    exit code = {rc}")

        print("\n[4] edit the plaintext, then status (expect: STALE again):")
        plain.write_text('{"api_key": "rotated_key_v2"}', encoding="utf-8")
        # Force the plaintext mtime to sit after the .enc so the check is
        # deterministic regardless of filesystem timestamp resolution.
        enc_mtime = os.path.getmtime(enc)
        os.utime(plain, (enc_mtime + 5, enc_mtime + 5))
        rc = secrets_guard.cmd_status()
        print(f"    exit code = {rc}  (re-encrypt before committing)")

        print("\n[5] re-encrypt the rotated secret:")
        secrets_guard.cmd_encrypt(PASSPHRASE)

        print("\n[6] simulate a fresh clone (only the .enc is present) then decrypt:")
        plain.unlink()
        secrets_guard.cmd_decrypt(PASSPHRASE)
        restored = plain.read_text(encoding="utf-8")
        assert restored == '{"api_key": "rotated_key_v2"}', "decrypt did not restore the rotated secret"
        print(f"    restored plaintext = {restored}  <- round-trip OK")
        return 0
    finally:
        secrets_guard.TARGETS = saved_targets
        os.environ.pop("SECRETS_GUARD_PASSWORD", None)
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    rc = demo_byte_api()
    if rc != 0:
        return rc
    rc = demo_file_workflow()
    if rc != 0:
        return rc

    print("\nThis is what keeps your encrypted config/db safe in a private backup repo:")
    print("the .enc blob is useless without the master password, any edit breaks the tag,")
    print("and `status` stops you from committing a plaintext that has drifted ahead of its .enc.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
