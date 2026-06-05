#!/usr/bin/env python3
"""ui/web/passwords.py — admin password hashing (Phase A auth), stdlib-only.

Split out of ``admin.py`` so the password format has **one source of truth** and the
offline ``set_password.py`` CLI can hash a password **without importing Flask** (it must
keep working even when the web stack / venv is broken — that is the whole point of a
recovery tool). ``admin.py`` re-exports these so its callers and tests are unchanged.

The stored form is self-describing: ``pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>``.
It never contains the plaintext; the random per-call salt makes each hash unique even for
the same password. Verification reads the iteration count back out of the stored string,
so a hash made with a different ``PBKDF2_ROUNDS`` still verifies — and it never raises on a
malformed stored value (returns False) so a garbage config can't crash the login path.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

# Cost factor (kept in step with admin.py's historical value) and the minimum length a new
# password must meet — shared by the web change-password route and the offline CLI.
PBKDF2_ROUNDS = 200_000
MIN_PASSWORD_LEN = 8


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, rounds_s, salt_hex, hash_hex = str(stored).split("$")
        if scheme != "pbkdf2_sha256":
            return False
        expected = bytes.fromhex(hash_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                 bytes.fromhex(salt_hex), int(rounds_s))
    except (ValueError, AttributeError):
        return False
    return hmac.compare_digest(dk, expected)
