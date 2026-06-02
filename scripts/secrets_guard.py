"""
secrets_guard.py — Encrypt/decrypt sensitive files for safe git storage.
========================================================================
Stdlib only (zero external dependencies). HMAC-CTR stream cipher.

Configure TARGETS below to point at your project's sensitive files.
Example defaults assume two common cases:
  - a config file containing secrets  (e.g. config.json)
  - a local database with secrets     (e.g. db/sensitive.db)

Usage:
  python secrets_guard.py encrypt              # Interactive password prompt (preferred)
  python secrets_guard.py decrypt              # Interactive password prompt
  SECRETS_GUARD_PASSWORD=... python secrets_guard.py encrypt   # Non-interactive via env var
  python secrets_guard.py encrypt --password X # Non-interactive (AVOID: visible in shell history / process list)
  python secrets_guard.py status               # Show encryption state

Developer workflow:
  1. Work normally with plaintext sensitive files (gitignored)
  2. Before commit: python secrets_guard.py encrypt
  3. git add <file>.enc ...
  4. git commit + push (only .enc files go to repo)

Restore workflow (after clone):
  1. git clone -> has *.enc files
  2. python secrets_guard.py decrypt -> restores plaintext
  3. Continue with normal setup

Crypto (format v2):
  - Key derivation: PBKDF2-HMAC-SHA256 (600,000 iterations, NIST SP 800-132 2023+)
  - Key separation: HKDF-Expand (RFC 5869) splits the PBKDF2 master into an
    independent cipher key and MAC key (domain separation)
  - Encryption: HMAC-based keystream in CTR mode (XOR)
  - Integrity: HMAC-SHA256 authentication tag (authenticates the header too)
  - Format: magic(3) || version(1) || salt(16) || hmac_tag(32) || ciphertext
            (the magic+version header makes the format self-identifying and
             cleanly migratable: bump FORMAT_VERSION and branch in decrypt_bytes)
  - Backward compatibility: v1 blobs (200k iters, single key for cipher+MAC) still
    decrypt; new encryptions are written as v2.

CAVEAT — read before relying on this:
  This is a CUSTOM construction built from stdlib primitives, NOT an audited crypto
  library. The pieces are sound (encrypt-then-MAC, constant-time tag compare, unique
  per-encryption salt/nonce, 600k-iter PBKDF2, HKDF-separated cipher/MAC keys) and it is
  adequate for keeping a private backup encrypted AT REST. But it has had no third-party
  cryptographic review. If you have a real adversarial threat model, use a vetted tool
  (age, sops, libsodium) and accept the dependency — this kit stays stdlib-only by design
  and cannot. See docs/SECURITY.md. Prefer the interactive password prompt over
  --password (which is visible in shell history and the process list).

Copyright: (c) 2026 doivamong
"""

import argparse
import getpass
import hashlib
import hmac
import os
import sys

# Print UTF-8 safely on a legacy Windows console / redirected stdout, so the
# status output never aborts with UnicodeEncodeError.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Resolve project root relative to this script (assumed to live in a 'scripts/' subdir).
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# CONFIGURE: list the (plaintext_path, encrypted_path) pairs you want to
# protect.  Paths are relative to BASE_DIR.  Adjust to match your project.
# ---------------------------------------------------------------------------
TARGETS = [
    (
        os.path.join(BASE_DIR, "config.json"),
        os.path.join(BASE_DIR, "config.json.enc"),
    ),
    (
        os.path.join(BASE_DIR, "db", "sensitive.db"),
        os.path.join(BASE_DIR, "db", "sensitive.db.enc"),
    ),
]

PBKDF2_ITERATIONS = 600_000      # v2 default (NIST SP 800-132, 2023+)
PBKDF2_ITERATIONS_V1 = 200_000   # legacy: only for decrypting existing v1 blobs
SALT_LEN = 16
HMAC_LEN = 32  # SHA-256 output length

# Format header: a 3-byte magic + 1-byte version, so the on-disk format is
# self-identifying and a future construction change can be migrated cleanly
# (bump FORMAT_VERSION and branch in decrypt_bytes). The header is authenticated
# by the HMAC tag, so the magic/version cannot be silently altered or downgraded.
MAGIC = b"AWB"
FORMAT_VERSION = 2               # current; v1 still decrypts (see _derive_keys)
SUPPORTED_VERSIONS = (1, 2)
HEADER = MAGIC + bytes([FORMAT_VERSION])
HEADER_LEN = len(HEADER)  # 4


# ── Crypto primitives (stdlib only) ─────────────────────────────────────────


def _hkdf_expand(prk: bytes, info: bytes, length: int = 32) -> bytes:
    """HKDF-Expand (RFC 5869) over HMAC-SHA256. ``prk`` is the PBKDF2 master key,
    already pseudorandom, so Extract is unnecessary — Expand alone gives us cheap
    domain separation into independent sub-keys."""
    out, block, counter = b"", b"", 1
    while len(out) < length:
        block = hmac.new(prk, block + info + bytes([counter]), "sha256").digest()
        out += block
        counter += 1
    return out[:length]


def _derive_keys(password: str, salt: bytes, version: int) -> tuple[bytes, bytes]:
    """Return ``(cipher_key, mac_key)`` for the given format version.

    v1 (legacy): 200k-iter PBKDF2, one key reused for both cipher and MAC.
    v2 (current): 600k-iter PBKDF2 master, then HKDF-Expand into two independent
    keys so the cipher key and the MAC key are domain-separated.
    """
    if version == 1:
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS_V1)
        return key, key
    master = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    cipher_key = _hkdf_expand(master, b"agent-workbench/secrets_guard cipher v2")
    mac_key = _hkdf_expand(master, b"agent-workbench/secrets_guard mac v2")
    return cipher_key, mac_key


def _hmac_ctr_crypt(data: bytes, key: bytes, nonce: bytes) -> bytes:
    """HMAC-CTR stream cipher: generate keystream via HMAC(key, nonce||counter).

    XOR-based — the same function is used for both encryption and decryption.
    Each block uses the full 32-byte HMAC-SHA256 output as its keystream chunk.
    """
    out = bytearray(len(data))
    block_size = 32  # SHA-256 output length
    for i in range(0, len(data), block_size):
        counter = i // block_size
        keystream = hmac.new(key, nonce + counter.to_bytes(8, "big"), "sha256").digest()
        chunk = data[i : i + block_size]
        for j, b in enumerate(chunk):
            out[i + j] = b ^ keystream[j]
    return bytes(out)


def encrypt_bytes(plaintext: bytes, password: str) -> bytes:
    """Encrypt plaintext bytes with the given password.

    Returns: magic(3) || version(1) || salt(16) || hmac_tag(32) || ciphertext
    """
    salt = os.urandom(SALT_LEN)
    cipher_key, mac_key = _derive_keys(password, salt, FORMAT_VERSION)

    # Derive a deterministic nonce from the salt so that the nonce is
    # never reused across independent encryptions.
    nonce = hashlib.sha256(salt + b"nonce").digest()[:16]
    ciphertext = _hmac_ctr_crypt(plaintext, cipher_key, nonce)

    # Authenticate the header + salt + ciphertext, so the magic/version cannot be
    # tampered with or downgraded without failing verification.
    tag = hmac.new(mac_key, HEADER + salt + ciphertext, "sha256").digest()

    return HEADER + salt + tag + ciphertext


def decrypt_bytes(encrypted: bytes, password: str) -> bytes:
    """Decrypt encrypted bytes with the given password.

    Input format: magic(3) || version(1) || salt(16) || hmac_tag(32) || ciphertext
    Returns the original plaintext bytes.
    Raises ValueError on a bad/unsupported format, wrong password, or tampered data.
    """
    if len(encrypted) < HEADER_LEN + SALT_LEN + HMAC_LEN:
        raise ValueError("File too short — not a valid encrypted format")

    header = encrypted[:HEADER_LEN]
    if header[:len(MAGIC)] != MAGIC:
        raise ValueError("Not an agent-workbench encrypted file (bad magic)")
    version = header[len(MAGIC)]
    if version not in SUPPORTED_VERSIONS:
        raise ValueError(
            f"Unsupported encrypted-format version {version} "
            f"(this build supports v{', v'.join(map(str, SUPPORTED_VERSIONS))})"
        )

    salt = encrypted[HEADER_LEN : HEADER_LEN + SALT_LEN]
    stored_tag = encrypted[HEADER_LEN + SALT_LEN : HEADER_LEN + SALT_LEN + HMAC_LEN]
    ciphertext = encrypted[HEADER_LEN + SALT_LEN + HMAC_LEN :]

    cipher_key, mac_key = _derive_keys(password, salt, version)

    # Verify the HMAC authentication tag (integrity + authentication), header included.
    expected_tag = hmac.new(mac_key, header + salt + ciphertext, "sha256").digest()
    if not hmac.compare_digest(stored_tag, expected_tag):
        raise ValueError("Wrong password or tampered data (HMAC mismatch)")

    nonce = hashlib.sha256(salt + b"nonce").digest()[:16]
    return _hmac_ctr_crypt(ciphertext, cipher_key, nonce)


# ── File operations ──────────────────────────────────────────────────────────


def encrypt_file(src: str, dst: str, password: str) -> bool:
    """Encrypt a single file.  Returns True on success."""
    if not os.path.isfile(src):
        print(f"  [SKIP] {os.path.basename(src)} — file not found")
        return False

    with open(src, "rb") as f:
        plaintext = f.read()
    encrypted = encrypt_bytes(plaintext, password)

    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    with open(dst, "wb") as f:
        f.write(encrypted)

    src_kb = len(plaintext) / 1024
    dst_kb = len(encrypted) / 1024
    print(
        f"  [OK] {os.path.basename(src)} ({src_kb:.1f} KB)"
        f" -> {os.path.basename(dst)} ({dst_kb:.1f} KB)"
    )
    return True


def decrypt_file(src: str, dst: str, password: str) -> bool:
    """Decrypt a single file.  Returns True on success."""
    if not os.path.isfile(src):
        print(f"  [SKIP] {os.path.basename(src)} — file not found")
        return False

    with open(src, "rb") as f:
        encrypted = f.read()
    try:
        plaintext = decrypt_bytes(encrypted, password)
    except ValueError as e:
        print(f"  [FAIL] {os.path.basename(src)}: {e}")
        return False

    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    with open(dst, "wb") as f:
        f.write(plaintext)

    print(
        f"  [OK] {os.path.basename(src)} -> {os.path.basename(dst)}"
        f" ({len(plaintext) / 1024:.1f} KB)"
    )
    return True


# ── Commands ─────────────────────────────────────────────────────────────────


def cmd_encrypt(password: str) -> int:
    """Encrypt all target files listed in TARGETS."""
    print("\n  Encrypting sensitive files...")
    ok = 0
    for plain, enc in TARGETS:
        if encrypt_file(plain, enc, password):
            ok += 1
    print(f"\n  Done: {ok}/{len(TARGETS)} file(s) encrypted.")
    if ok > 0:
        print("  Git: stage the *.enc files, commit, and push.")
        print("  Plaintext files should be gitignored — keep them out of version control.")
    return 0 if ok > 0 else 1


def cmd_decrypt(password: str) -> int:
    """Decrypt all target files listed in TARGETS."""
    print("\n  Decrypting sensitive files...")
    ok = 0
    for plain, enc in TARGETS:
        if decrypt_file(enc, plain, password):
            ok += 1
    print(f"\n  Done: {ok}/{len(TARGETS)} file(s) decrypted.")
    return 0 if ok > 0 else 1


def cmd_status() -> int:
    """Show encryption state of all targets.  Exits with code 1 if any .enc file is stale."""
    print("\n  Secrets Guard — Status")
    print(f"  {'=' * 50}")
    stale = False
    for plain, enc in TARGETS:
        name = os.path.basename(plain)
        has_plain = os.path.isfile(plain)
        has_enc = os.path.isfile(enc)
        if has_plain and has_enc:
            plain_mtime = os.path.getmtime(plain)
            enc_mtime = os.path.getmtime(enc)
            if plain_mtime > enc_mtime:
                delta_hours = (plain_mtime - enc_mtime) / 3600
                state = f"STALE — plaintext is {delta_hours:.0f}h newer than .enc (run: encrypt)"
                stale = True
            else:
                state = "OK (encrypted file is up-to-date)"
        elif has_plain:
            state = "PLAINTEXT only — not yet encrypted (run: encrypt)"
            stale = True
        elif has_enc:
            state = "ENCRYPTED only — needs decrypt"
        else:
            state = "MISSING (neither plaintext nor .enc exists)"
        print(f"  {name:30s} {state}")
    if stale:
        print("\n  [WARN] One or more .enc files are stale.")
        print("  Run: python scripts/secrets_guard.py encrypt")
        # Exit 1 so a pre-commit hook can block commits when .enc is out of date.
        return 1
    print("  All .enc files are up-to-date.")
    return 0


# ── CLI ──────────────────────────────────────────────────────────────────────


def _get_password(args) -> str:
    """Obtain the master password.

    Precedence: --password flag, then the SECRETS_GUARD_PASSWORD env var, then an
    OPTIONAL system keyring (only if the third-party `keyring` package is installed —
    the core stays stdlib-only and degrades silently when it is absent), then an
    interactive prompt. Prefer the prompt or the env var for non-interactive use:
    --password is visible in shell history and the process list (ps / Task Manager).
    """
    if args.password:
        return args.password
    env_pw = os.environ.get("SECRETS_GUARD_PASSWORD")
    if env_pw:
        return env_pw
    # Optional convenience: a system keyring (macOS Keychain, Windows Credential
    # Manager, Secret Service). Soft import — never a core dependency.
    try:
        import keyring  # type: ignore
        kp = keyring.get_password("agent-workbench", "secrets_guard")
        if kp:
            return kp
    except Exception:
        pass  # not installed / no backend -> fall through to the prompt
    try:
        pw = getpass.getpass("  Master password: ")
    except Exception:
        pw = input("  Master password: ")
    if not pw:
        print("  [!!] Password must not be empty.")
        sys.exit(1)
    return pw


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Secrets Guard — Encrypt/decrypt sensitive files for git storage",
    )
    ap.add_argument(
        "command",
        choices=["encrypt", "decrypt", "status"],
        help="encrypt: plaintext -> .enc | decrypt: .enc -> plaintext | status: show state",
    )
    ap.add_argument(
        "--password",
        metavar="PASS",
        help="Master password (non-interactive). AVOID: visible in shell history / "
             "process list — prefer the interactive prompt or the SECRETS_GUARD_PASSWORD env var.",
    )
    args = ap.parse_args()

    if args.command == "status":
        sys.exit(cmd_status())

    password = _get_password(args)

    if args.command == "encrypt":
        sys.exit(cmd_encrypt(password))
    elif args.command == "decrypt":
        sys.exit(cmd_decrypt(password))


if __name__ == "__main__":
    main()
