---
name: external-exec-allowlist-dir
description: "When a tool/hook shells out to an external binary, don't trust shutil.which/PATH blindly — accept it only if its directory is on a known-good allowlist (anti PATH-hijack). Salvaged concept from microsoft/markitdown (MIT)."
metadata: 
  type: feedback
---

Resolving an external executable via `shutil.which("tool")` (or bare PATH) means whatever
`tool[.exe]` appears first in `PATH` gets executed — a PATH-hijack / planted-binary vector. The
mitigation: after resolving, **accept the path only if its parent directory is on an allowlist of
known-good locations** (`/usr/bin`, `/usr/local/bin`, `/opt/...`, `C:\Windows\System32`,
`C:\Program Files`, ...), otherwise refuse and treat the tool as absent.

**Why:** a guard-focused kit that runs hooks/tools which shell out is exactly where a hijacked binary
does the most damage; "found on PATH" is not "trusted". This is a cheap, stdlib-only check
(`os.path.dirname` + a static allowlist) that fits a stdlib-only core.

**How to apply:** when any tool/hook execs a third-party binary, allowlist its directory before
running it; prefer an explicit env-var override (e.g. `EXIFTOOL_PATH`) first, then fall back to
`shutil.which` *gated by* the directory allowlist. Pattern seen in `microsoft/markitdown`
`_markitdown.py` (MIT) — salvaged as concept, no expression copied. Relates to a guard/hook surface
that shells out and [[security-feature-can-be-theater]] (verify the guard actually gates, don't
assume).
