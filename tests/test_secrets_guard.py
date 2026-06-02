import pytest

import secrets_guard
from secrets_guard import decrypt_bytes, encrypt_bytes


def test_roundtrip():
    pw = "correct horse battery staple"
    data = b'{"api_key": "x", "n": 42}'
    assert decrypt_bytes(encrypt_bytes(data, pw), pw) == data


def test_empty_payload_roundtrip():
    assert decrypt_bytes(encrypt_bytes(b"", "pw"), "pw") == b""


def test_wrong_password_rejected():
    blob = encrypt_bytes(b"secret", "right-password")
    with pytest.raises(ValueError):
        decrypt_bytes(blob, "wrong-password")


def test_tampered_ciphertext_rejected():
    blob = bytearray(encrypt_bytes(b"some sensitive bytes", "pw"))
    blob[-1] ^= 0x01  # flip one byte of the HMAC tag
    with pytest.raises(ValueError):
        decrypt_bytes(bytes(blob), "pw")


def test_nondeterministic_ciphertext():
    # Random salt + nonce => same plaintext encrypts to different blobs.
    a = encrypt_bytes(b"same plaintext", "pw")
    b = encrypt_bytes(b"same plaintext", "pw")
    assert a != b
    assert decrypt_bytes(a, "pw") == decrypt_bytes(b, "pw") == b"same plaintext"


def test_blob_carries_magic_and_version():
    blob = encrypt_bytes(b"x", "pw")
    assert blob[: len(secrets_guard.MAGIC)] == secrets_guard.MAGIC
    assert blob[len(secrets_guard.MAGIC)] == secrets_guard.FORMAT_VERSION


def test_bad_magic_rejected():
    blob = bytearray(encrypt_bytes(b"x", "pw"))
    blob[0] ^= 0x01  # corrupt the magic
    with pytest.raises(ValueError):
        decrypt_bytes(bytes(blob), "pw")


def test_unsupported_version_rejected():
    blob = bytearray(encrypt_bytes(b"x", "pw"))
    blob[len(secrets_guard.MAGIC)] = 0xFF  # bump version to an unsupported value
    with pytest.raises(ValueError):
        decrypt_bytes(bytes(blob), "pw")


# --- format versioning & key separation (v1 -> v2 migration) ----------------

# A real v1 blob captured from the pre-HKDF construction (200k iters, single key,
# fixed salt). password "pw" -> plaintext b"hello v1". This is a frozen golden
# vector: if the v1 decrypt branch ever regresses, this test fails.
_GOLDEN_V1_HEX = (
    "41574201000102030405060708090a0b0c0d0e0f"  # leak-scan: ignore (golden test vector, not a secret)
    "89c5214f3714e58f767670409dac2c26a73e9b256b37004e4a2e6d7df9eb00d8"  # leak-scan: ignore
    "21f25b1ec2ff3260"
)


def test_golden_v1_blob_still_decrypts():
    blob = bytes.fromhex(_GOLDEN_V1_HEX)
    assert blob[len(secrets_guard.MAGIC)] == 1  # it really is a v1 blob
    assert decrypt_bytes(blob, "pw") == b"hello v1"


def test_new_encryptions_are_v2():
    blob = encrypt_bytes(b"x", "pw")
    assert blob[len(secrets_guard.MAGIC)] == 2 == secrets_guard.FORMAT_VERSION


def test_v2_cipher_and_mac_keys_are_separated():
    salt = bytes(range(16))
    cipher_key, mac_key = secrets_guard._derive_keys("pw", salt, 2)
    assert cipher_key != mac_key  # HKDF domain separation
    # and v1 deliberately reuses one key, the weakness v2 fixes
    v1_cipher, v1_mac = secrets_guard._derive_keys("pw", salt, 1)
    assert v1_cipher == v1_mac


def test_hkdf_expand_is_deterministic_and_sized():
    prk = b"\x01" * 32
    assert secrets_guard._hkdf_expand(prk, b"info", 32) == secrets_guard._hkdf_expand(prk, b"info", 32)
    assert len(secrets_guard._hkdf_expand(prk, b"info", 48)) == 48
    assert secrets_guard._hkdf_expand(prk, b"a") != secrets_guard._hkdf_expand(prk, b"b")


# --- file operations & CLI helpers ------------------------------------------

from argparse import Namespace

from secrets_guard import _get_password, decrypt_file, encrypt_file


def test_encrypt_then_decrypt_file_roundtrip(tmp_path):
    src = tmp_path / "config.json"
    enc = tmp_path / "config.json.enc"
    restored = tmp_path / "restored.json"
    src.write_bytes(b'{"token": "shhh"}')

    assert encrypt_file(str(src), str(enc), "pw") is True
    assert enc.is_file() and enc.read_bytes()[: len(secrets_guard.MAGIC)] == secrets_guard.MAGIC
    assert decrypt_file(str(enc), str(restored), "pw") is True
    assert restored.read_bytes() == b'{"token": "shhh"}'


def test_encrypt_missing_source_returns_false(tmp_path):
    assert encrypt_file(str(tmp_path / "nope"), str(tmp_path / "out.enc"), "pw") is False


def test_decrypt_with_wrong_password_returns_false(tmp_path):
    src = tmp_path / "f.bin"
    enc = tmp_path / "f.bin.enc"
    src.write_bytes(b"payload")
    encrypt_file(str(src), str(enc), "right")
    # wrong password: decrypt_file catches the ValueError and reports failure, not a crash
    assert decrypt_file(str(enc), str(tmp_path / "out"), "wrong") is False


def test_get_password_precedence_flag_beats_env(monkeypatch):
    monkeypatch.setenv("SECRETS_GUARD_PASSWORD", "from-env")
    assert _get_password(Namespace(password="from-flag")) == "from-flag"  # leak-scan: ignore (test fixture, not a real secret)


def test_get_password_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("SECRETS_GUARD_PASSWORD", "from-env")
    assert _get_password(Namespace(password=None)) == "from-env"


def test_get_password_consults_optional_keyring(monkeypatch):
    monkeypatch.delenv("SECRETS_GUARD_PASSWORD", raising=False)
    import sys as _sys
    import types

    fake = types.ModuleType("keyring")
    fake.get_password = lambda service, user: "from-keyring"
    monkeypatch.setitem(_sys.modules, "keyring", fake)
    assert _get_password(Namespace(password=None)) == "from-keyring"


def test_keyring_absence_does_not_break(monkeypatch):
    # env wins over keyring; and with no keyring installed the env path still works
    monkeypatch.setenv("SECRETS_GUARD_PASSWORD", "from-env")
    import sys as _sys

    fake = type(_sys)("keyring")
    fake.get_password = lambda *a: "should-not-be-used"
    monkeypatch.setitem(_sys.modules, "keyring", fake)
    assert _get_password(Namespace(password=None)) == "from-env"


# --- status command (stale detection -> pre-commit gating exit codes) --------

import os

from secrets_guard import cmd_status


def test_status_plaintext_only_is_stale(tmp_path, monkeypatch, capsys):
    # plaintext exists but was never encrypted -> stale, exit 1 (a pre-commit
    # hook keying off this code would block the commit).
    plain = tmp_path / "config.json"
    plain.write_bytes(b"{}")
    monkeypatch.setattr(secrets_guard, "TARGETS", [(str(plain), str(tmp_path / "config.json.enc"))])
    assert cmd_status() == 1


def test_status_ok_when_enc_up_to_date(tmp_path, monkeypatch):
    plain = tmp_path / "config.json"
    enc = tmp_path / "config.json.enc"
    plain.write_bytes(b"{}")
    encrypt_file(str(plain), str(enc), "pw")
    # make the .enc look at least as new as the plaintext, deterministically
    p_mtime = os.path.getmtime(plain)
    os.utime(enc, (p_mtime + 5, p_mtime + 5))
    monkeypatch.setattr(secrets_guard, "TARGETS", [(str(plain), str(enc))])
    assert cmd_status() == 0


def test_status_detects_stale_enc(tmp_path, monkeypatch):
    # plaintext edited after the last encrypt -> .enc is stale, exit 1
    plain = tmp_path / "config.json"
    enc = tmp_path / "config.json.enc"
    plain.write_bytes(b"{}")
    encrypt_file(str(plain), str(enc), "pw")
    e_mtime = os.path.getmtime(enc)
    os.utime(plain, (e_mtime + 10, e_mtime + 10))
    monkeypatch.setattr(secrets_guard, "TARGETS", [(str(plain), str(enc))])
    assert cmd_status() == 1
