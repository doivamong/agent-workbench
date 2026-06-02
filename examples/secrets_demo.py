#!/usr/bin/env python3
"""Runnable demo for scripts/secrets_guard.py.

Shows an encrypt -> decrypt round-trip and that tampering is detected (the HMAC
integrity tag fails). Stdlib only.

    python examples/secrets_demo.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from secrets_guard import decrypt_bytes, encrypt_bytes  # noqa: E402


def main() -> int:
    password = "correct horse battery staple"  # leak-scan: ignore (demo passphrase)
    secret = b'{"api_key": "live_do_not_log_this", "db_password": "s3cr3t"}'

    print("Plaintext :", secret.decode())

    blob = encrypt_bytes(secret, password)
    print(f"Encrypted : {len(blob)} bytes (magic+version + salt + HMAC tag + ciphertext; nonce derived from salt)")

    back = decrypt_bytes(blob, password)
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
        decrypt_bytes(bytes(tampered), password)
        print("ERROR: tampered data should have failed")
        return 1
    except ValueError as e:
        print(f"Tampered  : rejected ({e})")

    print("\nThis is what keeps your encrypted config/db safe in a private backup repo:")
    print("the .enc blob is useless without the master password, and any edit breaks the tag.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
