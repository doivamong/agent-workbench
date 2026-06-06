"""Tests for tools/memory_audit.py."""
import memory_audit

_GOOD_FACT = """---
name: feedback-thing
description: A one-line description.
metadata:
  type: feedback
---

The fact. Related: [[feedback-thing]]
"""


def _mem(tmp_path, index_body: str, files: dict) -> None:
    (tmp_path / "MEMORY.md").write_text("# Memory Index\n\n" + index_body, encoding="utf-8")
    for name, body in files.items():
        (tmp_path / name).write_text(body, encoding="utf-8")


def test_clean_memory_has_no_errors(tmp_path):
    _mem(tmp_path, "- [feedback_thing.md](feedback_thing.md) - a thing\n",
         {"feedback_thing.md": _GOOD_FACT})
    findings = memory_audit.audit(tmp_path)
    assert [f for f in findings if f[0] == "error"] == []


def test_missing_frontmatter_is_error(tmp_path):
    _mem(tmp_path, "- [bad.md](bad.md)\n", {"bad.md": "no frontmatter here\n"})
    assert any(sev == "error" and "frontmatter" in msg for sev, _, msg in memory_audit.audit(tmp_path))


def test_invalid_type_is_error(tmp_path):
    fact = _GOOD_FACT.replace("type: feedback", "type: bogus")
    _mem(tmp_path, "- [feedback_thing.md](feedback_thing.md)\n", {"feedback_thing.md": fact})
    assert any(sev == "error" and "metadata.type" in msg for sev, _, msg in memory_audit.audit(tmp_path))


def test_dangling_index_link_is_error(tmp_path):
    _mem(tmp_path, "- [gone.md](gone.md) - missing file\n", {})
    assert any(sev == "error" and "missing file" in msg for sev, _, msg in memory_audit.audit(tmp_path))


def test_orphan_fact_is_warning(tmp_path):
    _mem(tmp_path, "(empty index)\n", {"feedback_thing.md": _GOOD_FACT})
    findings = memory_audit.audit(tmp_path)
    assert any(sev == "warn" and "orphan" in msg for sev, _, msg in findings)
    assert [f for f in findings if f[0] == "error"] == []


def test_parse_frontmatter_reads_nested_type():
    fm = memory_audit.parse_frontmatter(_GOOD_FACT)
    assert fm["name"] == "feedback-thing"
    assert fm["metadata"]["type"] == "feedback"


def test_main_exit_code(tmp_path):
    _mem(tmp_path, "- [feedback_thing.md](feedback_thing.md)\n", {"feedback_thing.md": _GOOD_FACT})
    assert memory_audit.main([str(tmp_path)]) == 0
    (tmp_path / "broken.md").write_text("nope\n", encoding="utf-8")
    assert memory_audit.main([str(tmp_path)]) == 1


# --- near-dup / size-budget checks (N2) ---

def _fact(name: str, desc: str, typ: str = "feedback") -> str:
    return f"---\nname: {name}\ndescription: {desc}\nmetadata:\n  type: {typ}\n---\n\nbody\n"


def test_near_duplicate_descriptions_warn(tmp_path):
    same = "deploy the staging server every friday afternoon"
    _mem(tmp_path, "- [a.md](a.md)\n- [b.md](b.md)\n",
         {"a.md": _fact("alpha", same), "b.md": _fact("beta", same)})
    findings = memory_audit.audit(tmp_path)
    assert any(sev == "warn" and "near-duplicate" in msg for sev, _, msg in findings)
    assert [f for f in findings if f[0] == "error"] == []  # detect-only, never an error


def test_near_duplicate_warn_points_at_consolidate_remedy(tmp_path):
    # The measurable near-dup trigger must self-surface its deferred remedy (governance section 7).
    same = "deploy the staging server every friday afternoon"
    _mem(tmp_path, "- [a.md](a.md)\n- [b.md](b.md)\n",
         {"a.md": _fact("alpha", same), "b.md": _fact("beta", same)})
    msg = next(m for sev, _, m in memory_audit.audit(tmp_path) if "near-duplicate" in m)
    assert "consolidate" in msg and "section 7" in msg


def test_distinct_descriptions_no_near_dup(tmp_path):
    _mem(tmp_path, "- [a.md](a.md)\n- [b.md](b.md)\n",
         {"a.md": _fact("alpha", "cats sleep all day long"),
          "b.md": _fact("beta", "quarterly financial reports are due")})
    assert not any("near-duplicate" in msg for _, _, msg in memory_audit.audit(tmp_path))


def test_oversized_index_entry_warn(tmp_path):
    long_line = "- [a.md](a.md) - " + "x" * 250
    _mem(tmp_path, long_line + "\n", {"a.md": _fact("alpha", "a short description")})
    assert any(sev == "warn" and "chars" in msg for sev, _, msg in memory_audit.audit(tmp_path))


def test_total_kb_budget_warn(tmp_path, monkeypatch):
    monkeypatch.setattr(memory_audit, "TOTAL_FACTS_MAX_KB", 0)  # force the budget to bite
    _mem(tmp_path, "- [a.md](a.md)\n", {"a.md": _fact("alpha", "a short description")})
    assert any(sev == "warn" and "KB" in msg for sev, _, msg in memory_audit.audit(tmp_path))


# --- flat-vs-nested type tolerance (C5) ---

def _flat_fact(name: str, desc: str, typ: str = "feedback") -> str:
    """ITF-style frontmatter: a flat top-level 'type:' rather than nested metadata.type."""
    return f"---\nname: {name}\ndescription: {desc}\ntype: {typ}\n---\n\nbody\n"


def test_flat_type_is_not_an_error(tmp_path):
    # A flat top-level 'type:' (the format a migrated corpus ships) must NOT false-error.
    _mem(tmp_path, "- [feedback_x.md](feedback_x.md)\n",
         {"feedback_x.md": _flat_fact("feedback-x", "a flat-schema fact")})
    findings = memory_audit.audit(tmp_path)
    assert [f for f in findings if f[0] == "error"] == []
    assert any(sev == "warn" and "flat top-level" in msg for sev, _, msg in findings)


def test_flat_invalid_type_still_errors(tmp_path):
    # Tolerance must not mask a genuine bad value on the flat path.
    _mem(tmp_path, "- [feedback_x.md](feedback_x.md)\n",
         {"feedback_x.md": _flat_fact("feedback-x", "bad type", typ="bogus")})
    assert any(sev == "error" and "not in" in msg for sev, _, msg in memory_audit.audit(tmp_path))


def test_nested_invalid_type_not_masked_by_flat(tmp_path):
    # Nested wins when present: a nested-garbage type errors even if a stray flat type is valid.
    body = "---\nname: feedback-x\ndescription: d\ntype: feedback\nmetadata:\n  type: bogus\n---\n\nbody\n"
    _mem(tmp_path, "- [feedback_x.md](feedback_x.md)\n", {"feedback_x.md": body})
    assert any(sev == "error" and "bogus" in msg for sev, _, msg in memory_audit.audit(tmp_path))


# --- name/filename identity (C4b) ---

def test_name_filename_mismatch_warns_never_errors(tmp_path):
    _mem(tmp_path, "- [feedback_misnamed.md](feedback_misnamed.md)\n",
         {"feedback_misnamed.md": _fact("totally-different", "drifted name")})
    findings = memory_audit.audit(tmp_path)
    assert any(sev == "warn" and "does not match filename" in msg for sev, _, msg in findings)
    assert [f for f in findings if f[0] == "error"] == []


def test_name_matches_filename_under_folding_no_warn(tmp_path):
    # name 'feedback-x' <-> file 'feedback_x.md' is the canonical convention: no identity warn.
    _mem(tmp_path, "- [feedback_x.md](feedback_x.md)\n",
         {"feedback_x.md": _fact("feedback-x", "a well-named fact")})
    assert not any("does not match filename" in msg for _, _, msg in memory_audit.audit(tmp_path))


# --- index byte budget (C4a) ---

def test_index_byte_budget_warn_when_line_checks_pass(tmp_path, monkeypatch):
    # An index can pass line-count AND per-line-char checks yet blow the byte budget.
    monkeypatch.setattr(memory_audit, "INDEX_MAX_BYTES", 100)
    body = "- [a.md](a.md) - " + "x" * 150  # one line, well under per-line and line-count limits
    _mem(tmp_path, body + "\n", {"a.md": _fact("alpha", "d")})
    findings = memory_audit.audit(tmp_path)
    assert any(sev == "warn" and "KB" in msg and "truncat" in msg for sev, _, msg in findings)
    # the per-line-char and line-count warnings must NOT be what fired here
    assert not any("chars" in msg for _, _, msg in findings)


def test_index_byte_budget_warn_points_at_archival_remedy(tmp_path, monkeypatch):
    # The measurable byte-budget trigger must self-surface its deferred remedy (governance section 7).
    monkeypatch.setattr(memory_audit, "INDEX_MAX_BYTES", 100)
    _mem(tmp_path, "- [a.md](a.md) - " + "x" * 150 + "\n", {"a.md": _fact("alpha", "d")})
    msg = next(m for sev, _, m in memory_audit.audit(tmp_path) if "truncat" in m)
    assert "archiv" in msg and "section 7" in msg


def test_small_index_no_byte_warn(tmp_path):
    _mem(tmp_path, "- [a.md](a.md)\n", {"a.md": _fact("alpha", "d")})
    assert not any("truncat" in msg for _, _, msg in memory_audit.audit(tmp_path))


def test_index_early_margin_warn_fires_at_80pct(tmp_path, monkeypatch):
    # make-it-go-red for the early-margin guardrail: an index >=80% of the byte budget (but still
    # UNDER 100%) must surface the aggregate pressure WARN BEFORE the hard truncation boundary, so
    # there is room to act. 204-byte index against a 220-byte budget == ~93%.
    monkeypatch.setattr(memory_audit, "INDEX_MAX_BYTES", 220)
    _mem(tmp_path, "- [a.md](a.md) - " + "x" * 170 + "\n", {"a.md": _fact("alpha", "d")})
    findings = memory_audit.audit(tmp_path)
    assert any(sev == "warn" and "early margin" in msg for sev, _, msg in findings)
    # it is the EARLY warn, not the hard 100% truncation warn (whose distinctive phrase is absent)
    assert not any("truncates near here" in msg for _, _, msg in findings)


def test_index_early_margin_warn_is_honest_about_being_a_margin(tmp_path, monkeypatch):
    # Copy must say it is an early margin (not the boundary), report the % of budget, and name the
    # §7 remedy — without overclaiming that recall has already truncated (ui-label-overclaim trap).
    monkeypatch.setattr(memory_audit, "INDEX_MAX_BYTES", 220)
    _mem(tmp_path, "- [a.md](a.md) - " + "x" * 170 + "\n", {"a.md": _fact("alpha", "d")})
    msg = next(m for sev, _, m in memory_audit.audit(tmp_path) if "early margin" in m)
    assert "NOT the truncation boundary" in msg and "section 7" in msg and "%" in msg


def test_index_below_soft_ratio_no_early_warn(tmp_path, monkeypatch):
    # Comfortably under the 80% margin: neither the early nor the hard byte WARN fires.
    monkeypatch.setattr(memory_audit, "INDEX_MAX_BYTES", 2000)
    _mem(tmp_path, "- [a.md](a.md) - " + "x" * 150 + "\n", {"a.md": _fact("alpha", "d")})
    findings = memory_audit.audit(tmp_path)
    assert not any("early margin" in msg for _, _, msg in findings)
    assert not any("truncat" in msg for _, _, msg in findings)


def test_index_line_count_warn(tmp_path, monkeypatch):
    # make-it-go-red for the 200-line index budget (mirrors the byte-gate test's discipline).
    monkeypatch.setattr(memory_audit, "INDEX_MAX_LINES", 1)
    _mem(tmp_path, "- [a.md](a.md)\n", {"a.md": _fact("alpha", "d")})
    assert any(sev == "warn" and "lines (> " in msg for sev, _, msg in memory_audit.audit(tmp_path))


# --- opt-in --promotion-readiness flag (buckets by metadata.group, never by name) ---

def _grouped_fact(name: str, group: str, desc: str = "d", typ: str = "feedback") -> str:
    return (f"---\nname: {name}\ndescription: {desc}\nmetadata:\n"
            f"  type: {typ}\n  group: {group}\n---\n\nbody\n")


def test_promotion_readiness_inactive_when_no_group(tmp_path):
    # Facts have names (they always do) but no metadata.group -> exactly the INACTIVE line. This
    # also proves names are NEVER a fallback bucket key (no "group <name>: 1 member" output).
    _mem(tmp_path, "- [alpha.md](alpha.md)\n- [beta.md](beta.md)\n",
         {"alpha.md": _fact("alpha", "one"), "beta.md": _fact("beta", "two")})
    assert memory_audit.promotion_readiness(tmp_path) == [
        "promotion grouping INACTIVE (no metadata.group present)"]


def test_promotion_readiness_reports_shared_group(tmp_path):
    # make-it-go-red: 3 facts sharing one metadata.group -> that group is reported as 3 members.
    files = {f"fact-{i}.md": _grouped_fact(f"fact-{i}", "config-reads") for i in range(3)}
    _mem(tmp_path, "".join(f"- [fact-{i}.md](fact-{i}.md)\n" for i in range(3)), files)
    assert memory_audit.promotion_readiness(tmp_path) == [
        "group config-reads: 3 member files - counts files, not distinct sessions; "
        "cannot prove recurrence"]


def test_promotion_readiness_buckets_by_group_not_name(tmp_path):
    # Three facts with DISTINCT names but the SAME group collapse into ONE group keyed by the
    # group value -- proving the bucket key is metadata.group, never the per-fact unique name.
    files = {"x.md": _grouped_fact("alpha", "shared"),
             "y.md": _grouped_fact("beta", "shared"),
             "z.md": _grouped_fact("gamma", "shared")}
    _mem(tmp_path, "- [x.md](x.md)\n- [y.md](y.md)\n- [z.md](z.md)\n", files)
    report = memory_audit.promotion_readiness(tmp_path)
    assert len(report) == 1
    assert report[0].startswith("group shared: 3 member files")


def test_promotion_readiness_flag_off_by_default(tmp_path, capsys):
    # Without the flag the default audit output carries nothing promotion-related.
    _mem(tmp_path, "- [alpha.md](alpha.md)\n", {"alpha.md": _grouped_fact("alpha", "g")})
    memory_audit.main([str(tmp_path)])
    assert "promotion" not in capsys.readouterr().out


def test_promotion_readiness_flag_adds_report(tmp_path, capsys):
    _mem(tmp_path, "- [alpha.md](alpha.md)\n", {"alpha.md": _grouped_fact("alpha", "g")})
    memory_audit.main([str(tmp_path), "--promotion-readiness"])
    out = capsys.readouterr().out
    assert "group g: 1 member files" in out
    assert "promote" not in out  # never the imperative 'promote' -- a hint, not a trigger
