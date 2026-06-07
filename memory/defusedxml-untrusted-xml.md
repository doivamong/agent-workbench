---
name: defusedxml-untrusted-xml
description: "stdlib xml.etree/minidom is unsafe on hostile XML (XXE, billion-laughs); parse untrusted XML with defusedxml. Caveat: defusedxml is NOT stdlib, so this can't live in a stdlib-only core — it's an awareness lesson for any future XML-parsing tool. From microsoft/markitdown (MIT)."
metadata: 
  type: feedback
---

Python's stdlib XML parsers (`xml.etree.ElementTree`, `xml.dom.minidom`) are **vulnerable to hostile
input** — external-entity expansion (XXE) and entity-expansion bombs (billion-laughs). Any tool that
parses XML from an untrusted source (a fetched file, a user-supplied doc, scraped content) should
parse it through `defusedxml` instead of the bare stdlib module.

**Why:** a kit that handles untrusted material (scanned files, fetched references) and a future tool
that naively `ET.parse()`s hostile XML is a real DoS / info-disclosure hole. Worth remembering
*before* writing such a tool, not after.

**Honest caveat:** `defusedxml` is a **third-party** dependency → it violates a stdlib-only core rule,
so it can only live in an opt-in / examples layer, never in the core (`scripts/`/`tools/`/hooks). In
the core, the only stdlib mitigation is limited (don't parse untrusted XML there, or pre-validate
size/structure). So this is an **awareness** lesson, not a code import.

**How to apply:** if a tool must parse untrusted XML and lives outside the stdlib core, depend on
`defusedxml` and parse via it; if it's core, avoid untrusted-XML parsing or push it to the opt-in
layer. Pattern seen in `microsoft/markitdown` (`_epub_converter.py`, `_rss_converter.py`, `omml.py`,
MIT) — salvaged as concept. Ties to the stdlib-only core rule and
[[optin-dep-tests-skipif-not-importorskip]].
