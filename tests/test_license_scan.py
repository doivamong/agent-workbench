"""tools/license_scan.py — the license / attribution marker tripwire.

It flags files whose text carries a license, copyright, or "adapted-from" marker, classifies each by
restriction, and — the load-bearing honesty — stays silent on a file with no marker (which is NOT
proof of original authorship, only the absence of a marker). These tests pin both directions.
"""
from pathlib import Path

import license_scan as ls


def _labels(text: str) -> set:
    return {label for label, _, _, _ in ls.scan_text(text)}


def test_flags_permissive_and_attribution():
    labels = _labels("Adapted from acme/widgets (Apache-2.0).")
    assert "permissive OSS (MIT / Apache / BSD / ISC / zlib)" in labels
    assert "attribution / provenance phrase" in labels


def test_flags_copyleft():
    assert "copyleft (GPL / AGPL / LGPL / MPL / EPL)" in _labels("Licensed under the GPLv3.")
    assert "copyleft (GPL / AGPL / LGPL / MPL / EPL)" in _labels("under AGPL-3.0")


def test_flags_noncommercial():
    assert "non-commercial (CC BY-NC / similar)" in _labels("Released under CC BY-NC 4.0.")


def test_flags_proprietary():
    assert "proprietary / all-rights-reserved" in _labels("ACME confidential. All rights reserved.")


def test_flags_third_party_copyright():
    assert "third-party copyright" in _labels("Copyright (c) 2021 Someone")


def test_flags_spdx():
    assert "SPDX license tag" in _labels("# SPDX-License-Identifier: MIT")


def test_clean_file_has_no_markers():
    assert ls.scan_text("def f():\n    return 42\n") == []


def test_one_hit_per_marker():
    # three copyright lines -> the copyright marker reports once, not three times
    text = "Copyright 2020 A\nCopyright 2021 B\nCopyright 2022 C\n"
    copyright_hits = [h for h in ls.scan_text(text) if h[0] == "third-party copyright"]
    assert len(copyright_hits) == 1


def test_scan_path_file_and_dir(tmp_path):
    (tmp_path / "a.py").write_text("# Apache-2.0\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("clean = True\n", encoding="utf-8")
    skipped = tmp_path / "node_modules"
    skipped.mkdir()
    (skipped / "c.py").write_text("# GPL\n", encoding="utf-8")
    results = ls.scan_path(tmp_path)
    assert (tmp_path / "a.py") in results
    assert (tmp_path / "b.py") not in results       # clean
    assert (skipped / "c.py") not in results         # node_modules is skipped


def test_scan_path_skips_non_text(tmp_path):
    (tmp_path / "img.png").write_bytes(b"\x89PNG GPL")  # non-text suffix -> not scanned
    assert ls.scan_path(tmp_path) == {}


def test_main_fail_on_find(tmp_path):
    (tmp_path / "v.py").write_text("# adapted from upstream/x (MIT)\n", encoding="utf-8")
    assert ls.main([str(tmp_path), "--fail-on-find"]) == 1
    assert ls.main([str(tmp_path)]) == 0            # without the flag, a finding is not an error


def test_main_clean_dir_returns_zero(tmp_path):
    (tmp_path / "ok.py").write_text("x = 1\n", encoding="utf-8")
    assert ls.main([str(tmp_path), "--fail-on-find"]) == 0


def test_main_missing_path_returns_2():
    assert ls.main(["/no/such/path/xyz123"]) == 2
