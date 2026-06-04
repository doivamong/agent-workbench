"""Tests for ops/release_pack.py — stdlib only. Packs the real kit payload into a
temp zip (fast) and round-trips verify/restore; no network, no write to the live kit."""
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ops.release_pack as rp  # noqa: E402


def test_payload_matches_install_copymap():
    files = rp.payload_files()
    arcs = [a for _, a in files]
    assert files, "payload should not be empty"
    assert len(arcs) == len(set(arcs)), "arcnames must be unique"
    # a known single-file COPY_MAP entry must be present (drift guard vs install.py)
    assert "scripts/secrets_guard.py" in arcs


def test_pack_verify_roundtrip(tmp_path):
    z = rp.pack(rel_dir=tmp_path, ver="testver")
    assert z.exists() and z.name == "awb-kit-testver.zip"
    with zipfile.ZipFile(z) as zf:
        assert rp.MANIFEST_NAME in zf.namelist()
    assert rp.verify(z) == []  # clean


def test_verify_detects_tamper(tmp_path):
    z = rp.pack(rel_dir=tmp_path, ver="v")
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(z) as zin, zipfile.ZipFile(tampered, "w") as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename != rp.MANIFEST_NAME and item.filename.endswith(".py"):
                data = data + b"\n# tamper\n"  # change bytes, keep the manifest sha
            zout.writestr(item, data)
    problems = rp.verify(tampered)
    assert any("sha mismatch" in p for p in problems)


def test_verify_non_release_zip(tmp_path):
    z = tmp_path / "x.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("a.txt", "hi")
    problems = rp.verify(z)
    assert problems and "missing" in problems[0].lower()


def test_restore_dry_then_apply(tmp_path):
    z = rp.pack(rel_dir=tmp_path, ver="v")
    target = tmp_path / "out"
    dry = rp.restore(z, target, dry=True)
    assert dry["result"] == "dry-run"
    assert not (target / "scripts" / "secrets_guard.py").exists()  # nothing written
    applied = rp.restore(z, target, dry=False)
    assert applied["result"] == "restored"
    assert (target / "scripts" / "secrets_guard.py").exists()


def test_restore_zip_slip_rejected(tmp_path):
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr(rp.MANIFEST_NAME, "{}")
        zf.writestr("../escape.txt", "pwned")
    import pytest
    with pytest.raises(ValueError):
        rp.restore(evil, tmp_path / "out", dry=False)
