# Getting Started

A ~10-minute walkthrough: run the demos (seconds each), then wire the tools into your own project.

🇻🇳 *Hướng dẫn ~10 phút: chạy thử các demo (vài giây mỗi cái), rồi gắn bộ tool vào dự án của bạn. Bản dịch đầy đủ README ở [README.vi.md](README.vi.md).*

## 0. Prerequisites

🇻🇳 *Yêu cầu — Python 3.10+ (lõi chỉ dùng stdlib; `pytest` chỉ cho bộ test). Git. Tuỳ chọn: Claude Code (hoặc agent khác) để dùng hooks và skills.*

- Python 3.10+ (the reusable core is stdlib-only; `pytest` is only for the test suite).
- Git. Optional: [Claude Code](https://claude.com/claude-code) (or another agent) to use the
  hooks and skills.

```bash
git clone https://github.com/doivamong/agent-workbench
cd agent-workbench
python -m pip install -r requirements.txt
```

## 1. See it work (each runs in seconds)

🇻🇳 *Xem nó chạy — mỗi lệnh dưới chạy trong vài giây; sau đó chạy `pytest` + `leak_scan` để tự chứng minh các tool đáng tin.*

```bash
python examples/secrets_demo.py             # encrypt/decrypt round-trip + tamper detection
python examples/hook_block_demo.py          # classifies safe vs dangerous shell commands
python examples/post_edit_simplify_demo.py  # the post-edit simplify-nudge classifier
python examples/invariant_demo.py           # the invariant gate catching rule violations
```

> **You should see:** `secrets_demo` prints `<- round-trip OK`, then *rejects* a tampered file;
> `hook_block_demo` ends with `All classifications correct.`; `invariant_demo` reports `found 3
> violation(s)` for the built-in rules and `found 1 violation(s)` for your one custom rule. None
> of these need `pip` — that's the point: the core is stdlib-only.

Then confirm the tools are actually trustworthy:

```bash
python -m pytest -q                 # the test suite
python tools/leak_scan.py . --entropy --fail-on-find --respect-gitignore   # this repo scans itself: 0 findings (same flags as CI)
```

## 2. Install into your project

🇻🇳 *Cài vào dự án — `install.py` chép hooks/skills/rules/tool/`secrets_guard`/scaffold memory, tuỳ chọn cài git pre-commit gate, rồi in đoạn `settings.json` để bạn merge.*

```bash
python install.py /path/to/your/project --with-git-hook
# --dry-run to preview; --force to overwrite existing files
```

This copies the hooks, skills, rules, tools, `secrets_guard`, and the memory scaffold into
your project, optionally installs a git pre-commit leak gate, and prints the `settings.json`
snippet you need. Merge that snippet into `your-project/.claude/settings.json`.

## 3. What you now have

🇻🇳 *Bạn có ngay — chặn lệnh Bash nguy hiểm, gắn cờ prompt mơ hồ, từ chối commit làm rò rỉ (nếu dùng `--with-git-hook`), cùng skills và scaffold memory.*

Open your project in Claude Code (or your agent). Immediately:

- **Dangerous `Bash` commands are blocked** (force-push, `rm -rf /`, `DROP TABLE`, …) by a
  `PreToolUse` hook.
- **Vague prompts get flagged** to be refined first, by a `UserPromptSubmit` hook.
- **Commits that leak a secret are refused** (if you used `--with-git-hook`).
- **Skills** under `.claude/skills/` and a **memory** scaffold under `memory/` (a reference
  template — your live corpus lives at the per-project path; see "Make it yours" below).

## 4. Make it yours

🇻🇳 *Biến thành của bạn — thay skills/invariants/deny-list bằng cái thật của dự án; trỏ memory về đúng path per-project rồi chạy `memory_recall_doctor` để kiểm tra wiring.*

- **Skills:** copy `.claude/skills/SKILL_TEMPLATE.md` and write playbooks for your workflow;
  keep `.claude/skills/skill-registry.md` in sync. See
  [`.claude/skills/README.md`](../.claude/skills/README.md).
- **Invariants:** replace `SAMPLE_INVARIANTS` in `tools/invariants.py` with your project's real
  "must never break" rules. Enable the invariants hook in `.pre-commit-config.yaml`.
- **Leak scanner:** keep a private deny-list (gitignored) of your project's identifiers and run
  `python tools/leak_scan.py . --denylist your-denylist.txt` to verify exports.
- **Memory — in 6 steps** (the copied `memory/` is a template; *live recall reads a different
  directory*, which is the part that trips people up):
  1. **Don't** edit this repo's `memory/` for live recall — it holds **example facts to replace**.
  2. Find your live dir: Claude Code (v2.1.59+) auto-loads `MEMORY.md` from the per-project path
     `~/.claude/projects/<id>/memory/` (or wherever `autoMemoryDirectory` points).
  3. Add one real fact there as a `kebab-name.md` file.
  4. Add one line linking it from that directory's `MEMORY.md` index.
  5. Run `python tools/memory_recall_doctor.py` to verify the wiring.
  6. Confirm the agent recalls it next session. Full design + the why:
     [`memory/README.md`](../memory/README.md) · [`memory-governance.md`](memory-governance.md).
- **Project rules:** adapt [`../CLAUDE.md`](../CLAUDE.md) / [`../AGENTS.md`](../AGENTS.md) to your
  project's golden rules.

## 5. CI

🇻🇳 *CI — workflow kèm sẵn chạy leak scan + invariants + tests mỗi push/PR; kit tự gate bằng chính tool của nó. Dùng lại mẫu này cho dự án bạn.*

The included [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs the leak scan,
invariants, and tests on every push/PR — the kit gates itself with its own tools. Reuse the
same pattern in your project.
