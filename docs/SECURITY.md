# Security model & threat model

This kit ships security-*adjacent* tooling — a dangerous-command hook, a secret/identifier
leak scanner, and a file encryptor. They are **safety rails and tripwires**, tuned to catch
the *accidental* footgun and the *obvious* mistake. None of them is an enforced security
boundary against a motivated adversary. This page states, per component, what each one **does**
and **does not** defend against, so you adopt them with the right expectations.

The guiding principle (same as the rest of the repo): *best-fit, honest about limits, not gospel.*

---

## `block_dangerous.py` — PreToolUse command guard

**Does:** catches common destructive shell commands before the agent runs them — `rm -rf /`
and its spacing/flag-order/casing variants, `find -delete`, `dd` to a raw device, `mkfs`,
recursive `chmod 777`, fork bombs, force-push, `git reset --hard`, file-zeroing
(`truncate -s 0`, content-less `> file`), and SQL `DROP`/`TRUNCATE`/`DELETE`-without-WHERE.
Matching runs on a whitespace-normalized, lowercased command. On an **unparseable payload it
fails CLOSED** (denies by default).

**Does NOT:** stop a determined operator. It is a string/token matcher, so base64, `eval`,
here-docs, variable indirection, or piping through another interpreter all evade it. It is a
**seatbelt, not a vault** — it prevents the fat-finger and the blatant one-liner, not deliberate
circumvention. Do not grant an agent destructive ambient authority and rely on this as the only
control.

## `prompt-refiner-inject.py` — UserPromptSubmit advisory

**Does:** flags vague, multi-part prompts so they get refined before work starts. **Does NOT:**
enforce anything — it is advisory, fail-open, and can be bypassed (`raw:` prefix, kill-switch
env vars). No security claim.

## `leak_scan.py` — commit-time leak tripwire

**Does:** flags common secret/identifier shapes (private keys, AWS `AKIA` keys, Slack/Telegram
tokens, `api_key=`/`password=` assignments, home paths, real-looking emails), an optional
project-specific deny-list (`--denylist`, gitignored), and — with `--entropy` — high-entropy
base64/hex tokens that match no keyword. Output is redacted (the matched value is never echoed).
A bare `# leak-scan: ignore` silences only *soft* detectors; **high-confidence secrets (private
key, AWS, Slack, Telegram) require a named opt-out** (`# leak-scan: ignore[aws_access_key]`), so a
real credential can't be hidden by an accidental blanket comment.

**Does NOT:** find everything. It is **line-based** (a secret split across lines, or a token with
no recognizable shape and below the entropy threshold, slips through) and has false negatives by
design. **It is not a replacement for a dedicated scanner.** Use it as a fast pre-commit tripwire
*in addition to* a real backstop:

- [gitleaks](https://github.com/gitleaks/gitleaks) or [trufflehog](https://github.com/trufflesecurity/trufflehog) in CI, and
- **GitHub secret scanning + push protection** on the repo (already enabled on this one).

If a real secret ever reaches a commit, rotate it — scrubbing history is not enough once it's pushed.

## `secrets_guard.py` — at-rest file encryptor

**Does:** encrypt sensitive files for storage with a **custom stdlib construction**:
PBKDF2-HMAC-SHA256 (200k iterations) → HMAC-keystream CTR cipher → encrypt-then-MAC with an
HMAC-SHA256 tag and constant-time verification, unique random salt (and derived nonce) per
encryption. It round-trips correctly and rejects tampering and wrong passwords. Adequate for
keeping a **private backup encrypted at rest**.

**Does NOT:** stand in for an audited cryptographic library. This construction has had **no
third-party cryptographic review**, has no algorithm-versioning field for future migration, and
derives the cipher key and MAC key from the same PBKDF2 output (no HKDF separation). The kit is
**stdlib-only by golden rule**, so it cannot depend on a vetted library — that is a deliberate
scope trade-off, not an endorsement of rolling your own crypto. **If you have a real adversarial
threat model, use [`age`](https://github.com/FiloSottile/age), [`sops`](https://github.com/getsops/sops),
or libsodium and accept the dependency.**

Password handling, in precedence order:
1. **Interactive prompt** (default; `getpass`) — preferred.
2. **`SECRETS_GUARD_PASSWORD` env var** — for non-interactive/CI use.
3. **`--password` flag** — **avoid**: it is visible in shell history and the process list
   (`ps`, Task Manager). Use the prompt or the env var instead.

---

## Reporting a problem

This is a single-maintainer MIT learning artifact, not a product with an SLA. If you spot a
vulnerability or a leaked value, open an issue — **without quoting the sensitive value itself** —
or contact the maintainer. There is no formal disclosure process beyond that.
