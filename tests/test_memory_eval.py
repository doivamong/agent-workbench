import json
from pathlib import Path

import pytest

import memory_eval

REPO_ROOT = Path(__file__).resolve().parents[1]
EM = "—"  # em-dash, as the real MEMORY.md uses


def _fact(name: str, body: str = "body text") -> str:
    return f"---\nname: {name}\ndescription: a fact.\nmetadata:\n  type: feedback\n---\n\n{body}\n"


# --- tokenize / parse_index ------------------------------------------------

def test_tokenize_lowercases_and_splits():
    assert memory_eval._tokenize("Robocopy /MOVE Works!") == {"robocopy", "move", "works"}


def test_parse_index_handles_em_dash_and_mismatched_link_text():
    index = (
        "# Memory Index\n\n"
        "## A header to skip\n"
        "> a blockquote to skip\n"
        f"- [Human Readable Title](windows-locked-dir-rename-robocopy.md) {EM} dir rename handle lock\n"
        f"- [Another](sqlite-live-read-mode-ro.md) {EM} read only mode\n"
    )
    mapping = memory_eval.parse_index(index)
    assert set(mapping) == {"windows-locked-dir-rename-robocopy.md", "sqlite-live-read-mode-ro.md"}
    # the hook is the text AFTER the em-dash, not the bracket title
    assert mapping["windows-locked-dir-rename-robocopy.md"] == "dir rename handle lock"


def test_parse_index_tolerates_ascii_dash_fallback():
    mapping = memory_eval.parse_index("- [a](feedback_a.md) - a hook\n")
    assert mapping["feedback_a.md"] == "a hook"


def test_parse_index_against_real_corpus_is_nonempty_and_resolves():
    """Guard the blocker the plan review caught: the parser must work on the REAL MEMORY.md
    (em-dash, link-text != filename), not just hand-made fixtures - or the index arm measures
    an empty corpus."""
    mem = REPO_ROOT / "memory"
    mapping = memory_eval.parse_index((mem / "MEMORY.md").read_text(encoding="utf-8"))
    assert len(mapping) >= 20, "real index parsed too few entries - format drift?"
    for fname in mapping:
        assert (mem / fname).exists(), f"index hook points at a missing file: {fname}"


# --- ranking ----------------------------------------------------------------

def test_rank_orders_by_overlap_and_drops_zero_score():
    docs = {
        "hit.md": "windows robocopy handle lock rename",
        "weak.md": "windows only",
        "miss.md": "totally unrelated content here",
    }
    ranked = memory_eval.rank("windows robocopy handle lock", docs)
    assert ranked[0] == "hit.md"
    assert "miss.md" not in ranked  # zero overlap is never credited by a tie-break


# --- metrics ----------------------------------------------------------------

def test_query_metrics_known_case():
    ranked = ["a.md", "b.md", "c.md"]
    recall, precision = memory_eval._query_metrics(ranked, ["b.md"], k=3)
    assert recall == 1.0
    assert precision == pytest.approx(1 / 3)


def test_query_metrics_recall_zero_when_gold_below_cutoff():
    ranked = ["a.md", "b.md", "c.md"]
    recall, _ = memory_eval._query_metrics(ranked, ["c.md"], k=1)  # c is rank 3, not in top-1
    assert recall == 0.0


def test_reciprocal_rank():
    assert memory_eval._reciprocal_rank(["a.md", "b.md"], ["b.md"]) == pytest.approx(0.5)
    assert memory_eval._reciprocal_rank(["a.md"], ["z.md"]) == 0.0  # a miss scores 0


# --- evaluate (end to end on a temp corpus) ---------------------------------

def _make_corpus(d: Path):
    (d / "MEMORY.md").write_text(
        "# Memory Index\n\n"
        f"- [Robocopy fix](robocopy.md) {EM} windows directory rename permission denied robocopy\n"
        f"- [Sqlite ro](sqlite.md) {EM} sqlite read only mode wal checkpoint\n",
        encoding="utf-8")
    (d / "robocopy.md").write_text(_fact("robocopy", "windows rename robocopy move handle lock"), encoding="utf-8")
    (d / "sqlite.md").write_text(_fact("sqlite", "sqlite read only wal checkpoint bytes"), encoding="utf-8")


def test_evaluate_index_recalls_gold(tmp_path):
    _make_corpus(tmp_path)
    gold = [{"query": "windows directory rename permission denied robocopy", "gold": ["robocopy.md"]}]
    res = memory_eval.evaluate(tmp_path, gold, ks=(1,))
    assert res["arms"]["index"]["recall"][1] == 1.0
    assert res["arms"]["body"]["recall"][1] == 1.0
    assert res["n_queries"] == 1


def test_evaluate_flags_unknown_gold_file(tmp_path):
    _make_corpus(tmp_path)
    gold = [{"query": "anything", "gold": ["does-not-exist.md"]}]
    res = memory_eval.evaluate(tmp_path, gold, ks=(1,))
    assert "does-not-exist.md" in res["unknown_gold"]


# --- gold loading + CLI exit codes ------------------------------------------

def test_load_gold_valid(tmp_path):
    p = tmp_path / "g.json"
    p.write_text('[{"query": "q", "gold": ["a.md"]}]', encoding="utf-8")
    assert memory_eval.load_gold(p) == [{"query": "q", "gold": ["a.md"]}]


@pytest.mark.parametrize("bad", ['{"not": "a list"}', '[{"query": 1, "gold": []}]', '[{"query": "q"}]'])
def test_load_gold_rejects_malformed(tmp_path, bad):
    p = tmp_path / "g.json"
    p.write_text(bad, encoding="utf-8")
    with pytest.raises(ValueError):
        memory_eval.load_gold(p)


def test_main_missing_gold_file_exits_2(tmp_path):
    assert memory_eval.main(["--gold", str(tmp_path / "nope.json"), "--dir", str(tmp_path)]) == 2


def test_main_malformed_gold_exits_2(tmp_path):
    g = tmp_path / "g.json"
    g.write_text("{ not json", encoding="utf-8")
    assert memory_eval.main(["--gold", str(g), "--dir", str(tmp_path)]) == 2


def test_main_missing_dir_is_advisory_exit_0(tmp_path):
    g = tmp_path / "g.json"
    g.write_text('[{"query": "q", "gold": ["a.md"]}]', encoding="utf-8")
    rc = memory_eval.main(["--gold", str(g), "--dir", str(tmp_path / "no_such_dir")])
    assert rc == 0  # a measurement tool is advisory, not a CI gate


def test_main_happy_path_exit_0(tmp_path, capsys):
    _make_corpus(tmp_path)
    g = tmp_path / "g.json"
    g.write_text(json.dumps([{"query": "sqlite read only wal", "gold": ["sqlite.md"]}]), encoding="utf-8")
    rc = memory_eval.main(["--gold", str(g), "--dir", str(tmp_path)])
    assert rc == 0
    assert "Recall benchmark" in capsys.readouterr().out


# --- ASCII-safe output (a stray non-ASCII char crashes a legacy console) -----

def test_report_output_is_ascii_safe(tmp_path):
    _make_corpus(tmp_path)
    gold = [{"query": "windows robocopy", "gold": ["robocopy.md"]}]
    for line in memory_eval.format_report(memory_eval.evaluate(tmp_path, gold)):
        line.encode("ascii")  # raises UnicodeEncodeError if any non-ASCII slipped in
