import pytest

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
