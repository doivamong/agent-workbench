#!/usr/bin/env python3
"""memory_eval.py - does the index-gated MEMORY.md actually surface the right fact?

``memory_recall_doctor`` checks the WIRING (is the live dir loaded, is the index within the load
budget). This tool asks the next question - RECALL QUALITY: given a query, does the one-line index
hook rank the right fact file near the top? It is a tiny, stdlib retrieval benchmark over a
hand-labeled gold set, so you can MEASURE the index-gating discipline instead of asserting it.

How it models recall (faithfully, and honestly limited):

  - INDEX arm: score each ``MEMORY.md`` hook line (the one-liner whose job is to "decide relevance
    during recall") against the query by Jaccard token overlap, rank, take top-k. This is what the
    agent sees first each session.
  - BODY baseline: score each fact's FULL text the same way - what you'd get if the agent read
    every file (grep-everything). The gap between the two arms is what the cheap index buys (or
    costs). Jaccard is used (not a raw overlap COUNT) on purpose: a count scales with document
    length, so a long body would out-score a short hook regardless of relevance - the comparison
    would be decided by length, not retrieval. Jaccard normalises that away.
  - Metrics: recall@k, precision@k, MRR, averaged over the gold queries.

Does NOT: measure answer/QA quality (only whether the right FILE ranks - retrieval, not
correctness); model the live agent's semantic judgment (bag-of-words Jaccard is a deliberately
simple, transparent proxy - the real agent reads meaning, so treat these numbers as a FLOOR, not a
ceiling); validate the gold set (it is hand-labeled and usually small, and if you wrote both the
hooks and the gold it is self-labeled - a directional signal at n=small, never a leaderboard
score); rank files with zero token overlap (they are treated as not-retrieved, so a tie-break can
never credit a miss); write anything. Stdlib only.

Usage:
    python tools/memory_eval.py --gold examples/memory_eval_gold.json --dir memory
    python tools/memory_eval.py --gold gold.json              # default --dir: the live per-project dir
    python tools/memory_eval.py --gold gold.json --k 1,3,5,10

Gold-set JSON: a list of {"query": "...", "gold": ["fact-filename.md", ...]}.

Exit code: 2 on a missing/malformed --gold file (bad input you supplied). Everything else - a
missing memory dir, a healthy run - exits 0 (advisory; this is a measurement, not a CI gate).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:  # tools/ on sys.path: a direct script run, or the test suite (see tests/conftest.py)
    # reuse - never re-derive (defer-discipline). _desc_tokens is memory_audit's tokenizer; sharing
    # it keeps these Jaccard inputs identical to the near-duplicate detector's.
    from memory_audit import INDEX_NAME, SKIP, _desc_tokens as _tokenize, _jaccard
    from memory_recall_doctor import resolve_live_dir
except ModuleNotFoundError:  # imported as a package, e.g. `from tools.memory_eval import ...`
    from tools.memory_audit import INDEX_NAME, SKIP, _desc_tokens as _tokenize, _jaccard
    from tools.memory_recall_doctor import resolve_live_dir

# Markdown index link to a fact file, e.g. "[Some title](some-file.md)". Same idiom as
# memory_audit's dangling-link check (tools/memory_audit.py).
_LINK_RE = re.compile(r"\]\(([^)]+\.md)\)")
_EM_DASH = chr(0x2014)  # em-dash separator in MEMORY.md hooks; chr() keeps this source ASCII


def parse_index(index_text: str) -> "dict[str, str]":
    """Map fact-filename -> its one-line index hook, from the real MEMORY.md format.

    Handles the format the live index actually uses: an em-dash separator and link TEXT that
    differs from the filename (e.g. ``- [Verify before asserting](verify-load-bearing.md) - hook``).
    Lines with no ``](file.md)`` link - headers, blockquotes, blanks - are skipped.
    """
    out: "dict[str, str]" = {}
    for line in index_text.splitlines():
        m = _LINK_RE.search(line)
        if not m:
            continue
        fname = m.group(1).split("/")[-1]
        if _EM_DASH in line:
            hook = line.split(_EM_DASH, 1)[1].strip()
        else:  # tolerate an ASCII " - hook" fallback (the demo/sibling-fixture shape)
            hook = line[m.end():].lstrip(" -\t")
        out[fname] = hook
    return out


def read_bodies(mem_dir: Path) -> "dict[str, str]":
    """Map fact-filename -> full file text (the grep-everything baseline corpus)."""
    out: "dict[str, str]" = {}
    for p in sorted(mem_dir.glob("*.md")):
        if p.name in SKIP:
            continue
        out[p.name] = p.read_text(encoding="utf-8", errors="replace")
    return out


def rank(query: str, doc_map: "dict[str, str]") -> "list[str]":
    """Rank filenames by Jaccard overlap of query vs doc text. Score-0 docs are NOT ranked
    (a miss is a miss - never credited by a filename tie-break). Ties: score desc, filename asc."""
    qt = _tokenize(query)
    scored = [(_jaccard(qt, _tokenize(text)), fname) for fname, text in doc_map.items()]
    ranked = [(s, fname) for s, fname in scored if s > 0]
    ranked.sort(key=lambda t: (-t[0], t[1]))
    return [fname for _, fname in ranked]


def _query_metrics(ranked: "list[str]", gold: "list[str]", k: int) -> "tuple[float, float]":
    gold_set = set(gold)
    topk = ranked[:k]
    hits = sum(1 for f in topk if f in gold_set)
    recall = hits / len(gold_set) if gold_set else 0.0
    precision = hits / k if k else 0.0
    return recall, precision


def _reciprocal_rank(ranked: "list[str]", gold: "list[str]") -> float:
    gold_set = set(gold)
    for i, f in enumerate(ranked, 1):
        if f in gold_set:
            return 1.0 / i
    return 0.0


def evaluate(mem_dir: Path, gold: "list[dict]", ks: "tuple[int, ...]" = (1, 3, 5)) -> dict:
    """Run the index arm and the body baseline over the gold queries. Pure (dir + gold in,
    metrics out). Returns per-arm mean recall@k / precision@k / MRR plus any unknown gold files."""
    index_text = (mem_dir / INDEX_NAME).read_text(encoding="utf-8", errors="replace") \
        if (mem_dir / INDEX_NAME).exists() else ""
    arms = {"index": parse_index(index_text), "body": read_bodies(mem_dir)}

    on_disk = set(read_bodies(mem_dir))
    unknown = sorted({g for entry in gold for g in entry.get("gold", []) if g not in on_disk})

    n = len(gold)
    results: dict = {"n_queries": n, "ks": list(ks), "unknown_gold": unknown, "arms": {}}
    for arm, dmap in arms.items():
        rec = {k: 0.0 for k in ks}
        prec = {k: 0.0 for k in ks}
        mrr = 0.0
        for entry in gold:
            ranked = rank(entry["query"], dmap)
            for k in ks:
                r, p = _query_metrics(ranked, entry["gold"], k)
                rec[k] += r
                prec[k] += p
            mrr += _reciprocal_rank(ranked, entry["gold"])
        results["arms"][arm] = {
            "recall": {k: (rec[k] / n if n else 0.0) for k in ks},
            "precision": {k: (prec[k] / n if n else 0.0) for k in ks},
            "mrr": (mrr / n if n else 0.0),
        }
    return results


def format_report(results: dict) -> "list[str]":
    """ASCII-only report (a stray non-ASCII char crashes a legacy console - see the sibling tools)."""
    ks = results["ks"]
    lines = [f"Recall benchmark over {results['n_queries']} gold query(ies). Higher is better.",
             "  arm    | " + " | ".join(f"R@{k}".rjust(6) for k in ks)
             + " | " + " | ".join(f"P@{k}".rjust(6) for k in ks) + " |    MRR",
             "  -------+-" + "-+-".join("-" * 6 for _ in ks)
             + "-+-" + "-+-".join("-" * 6 for _ in ks) + "-+-------"]
    for arm in ("index", "body"):
        a = results["arms"][arm]
        cells = " | ".join(f"{a['recall'][k]:.3f}".rjust(6) for k in ks)
        pcells = " | ".join(f"{a['precision'][k]:.3f}".rjust(6) for k in ks)
        lines.append(f"  {arm:6} | {cells} | {pcells} | {a['mrr']:.3f}")
    lines.append("")
    lines.append("  index = the one-line MEMORY.md hooks (what the agent sees first each session)")
    lines.append("  body  = full fact text (grep-everything); the gap is what the index buys/costs")
    if results["unknown_gold"]:
        lines.append("  WARN: gold names not found on disk (typo?): "
                     + ", ".join(results["unknown_gold"]))
    lines.append("")
    lines.append("Honest limits: measures RETRIEVAL (did the right FILE rank), NOT answer quality;")
    lines.append("bag-of-words Jaccard is a transparent proxy - the live agent reads meaning, so")
    lines.append("real recall is likely >= these (a floor). A small, self-labeled gold set is a")
    lines.append("directional signal, not a score. Re-measure on a broader, independently-labeled set.")
    return lines


def load_gold(path: Path) -> "list[dict]":
    """Load + validate the gold JSON. Raises ValueError on a malformed structure."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("gold file must be a JSON list of {query, gold} objects")
    for i, entry in enumerate(data):
        if not isinstance(entry, dict) or not isinstance(entry.get("query"), str) \
                or not isinstance(entry.get("gold"), list) \
                or not all(isinstance(g, str) for g in entry["gold"]):
            raise ValueError(f"gold[{i}] must be {{'query': str, 'gold': [str, ...]}}")
    return data


def main(argv: "list[str] | None" = None) -> int:
    ap = argparse.ArgumentParser(
        description="Benchmark whether the MEMORY.md index recalls the right fact (read-only).")
    ap.add_argument("--gold", type=Path, required=True,
                    help="Gold-set JSON: [{'query': str, 'gold': [fact-filename, ...]}].")
    ap.add_argument("--dir", type=Path, default=None,
                    help="The memory dir to benchmark (default: the live per-project dir).")
    ap.add_argument("--project", type=Path, default=None,
                    help="Project root used to derive the live dir (default: cwd).")
    ap.add_argument("--k", default="1,3,5", help="Comma-separated cut-offs for recall@k (default 1,3,5).")
    args = ap.parse_args(argv)

    if not args.gold.exists():
        print(f"error: --gold {args.gold} not found.", file=sys.stderr)
        return 2
    try:
        gold = load_gold(args.gold)
    except (ValueError, json.JSONDecodeError) as e:
        print(f"error: --gold {args.gold} is malformed: {e}", file=sys.stderr)
        return 2
    try:
        ks = tuple(int(x) for x in str(args.k).split(",") if x.strip())
    except ValueError:
        print(f"error: --k {args.k!r} must be comma-separated integers.", file=sys.stderr)
        return 2
    if not ks:
        ks = (1, 3, 5)

    project = (args.project or Path.cwd()).resolve()
    live, how = resolve_live_dir(project, args.dir)  # (Path, str); existence NOT guaranteed
    if not live.is_dir():
        print(f"Memory dir not found: {live}\n  resolved via: {how}\n"
              "  Nothing to benchmark - pass --dir <path> to point at a real memory dir.")
        return 0  # advisory, not a failure (a measurement tool, not a gate)

    if not gold:
        print(f"Memory dir: {live}\n  resolved via: {how}\n  Gold set is empty - nothing to measure.")
        return 0

    print(f"Memory dir: {live}")
    print(f"  resolved via: {how}")
    for line in format_report(evaluate(live, gold, ks)):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
