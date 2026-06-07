# Getting Started

A ~10-minute walkthrough: run the demos (seconds each), then wire the tools into your own project.

🇻🇳 *Hướng dẫn ~10 phút: chạy thử các demo (vài giây mỗi cái), rồi gắn bộ tool vào dự án của bạn. Bản dịch đầy đủ README ở [README.vi.md](README.vi.md).*

## 0. Prerequisites

🇻🇳 *Yêu cầu — Python ≥ 3.10 (lõi chỉ dùng stdlib; `pytest` chỉ cho bộ test). Git. Tuỳ chọn: Claude Code (hoặc agent khác) để dùng hooks và skills.*

- **Python ≥ 3.10** (the reusable core is stdlib-only; `pytest` is only for the test suite — the
  CI matrix is 3.10 / 3.11 / 3.12).
- Git. Optional: [Claude Code](https://claude.com/claude-code) (or another agent) to use the
  hooks and skills.

```bash
git clone https://github.com/doivamong/agent-workbench
cd agent-workbench
python -m pip install -r requirements.txt
```

**Optional extras** — the stdlib-only core needs neither:

- To run *this repo's own* commit gates locally (the leak scan + invariants in
  [`.pre-commit-config.yaml`](../.pre-commit-config.yaml)):

```bash
pip install pre-commit && pre-commit install
```

- To run the **opt-in web dashboard** — its Flask + Jinja2 are the kit's *only* runtime
  dependency, isolated in `ui/web/` so the core stays stdlib-only
  (see [`ui/web/README.md`](../ui/web/README.md)):

```bash
pip install -r ui/web/requirements.txt
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

> **Prefer to just talk to Claude Code?** Clone agent-workbench and **open that folder** in Claude
> Code first, then say: *"install agent-workbench into `<path-to-my-project>` and confirm the guards
> are on."* The agent (skill `awb-install-and-verify`) runs the install below against your project,
> then `install.py … --doctor` to prove the guards actually fire — and tells you honestly what's
> protected and what isn't. It runs **from the kit folder**, not from inside your empty project (the
> tools aren't there yet).
>
> 🇻🇳 *Thích chỉ trò chuyện với Claude Code? Trước hết clone agent-workbench và **mở thư mục đó**
> trong Claude Code, rồi nói: "cài agent-workbench vào `<đường-dẫn-dự-án>` và xác nhận guard đã bật."
> Agent (skill `awb-install-and-verify`) chạy lệnh cài bên dưới rồi `--doctor` để chứng minh guard
> thực sự chạy, và nói thật cái gì được bảo vệ. Chạy **từ thư mục kit**, không phải từ trong dự án trống.*

```bash
python install.py /path/to/your/project --with-git-hook
python install.py /path/to/your/project --doctor   # then verify the wired guards actually fire
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

## 6. When a commit is refused (and who fixes it)

🇻🇳 *Khi commit bị từ chối — mỗi "gate" đỏ là một lằn ranh an toàn đang làm việc, không phải lỗi của bạn. Bảng dưới dịch từng gate sang lời thường và "ai sửa": trong mọi trường hợp, **agent sửa, không phải bạn** — chỉ cần nói "commit bị từ chối". Chi tiết: [pre-commit-failure-modes.md](pre-commit-failure-modes.md).*

A refused commit is a guard doing its job, not a mistake on your part. Seven gates can turn a commit
(or a CI run) red. Here is what each means in plain words — and in every case **the agent fixes it,
not you**:

| Gate | When it is red, it means | Where it runs |
|---|---|---|
| leak scan | a secret, identifier, or absolute machine path slipped into a tracked file | local + CI |
| pytest | a test failed — something the code promised stopped being true | local + CI |
| codebase invariants | a project "must never break" rule tripped (e.g. a debug `print` left in a library) | local + CI |
| skill registry lint | a skill file and the registry that lists it drifted apart | local + CI |
| context budget | the skill set grew past its size cap (a bloat guard) | local + CI |
| manifest sync | the set of files on disk no longer matches the recorded manifest | local + CI |
| README metrics | a count in the README (tools, tests, …) no longer matches reality | CI only |

The first six run on every local commit and again in CI; the seventh runs only in CI. None of them
ask you to read a traceback — tell the agent "the commit was refused" and it diagnoses and fixes the
cause. The [pre-commit-failure-modes.md](pre-commit-failure-modes.md) registry explains how these
gates learn from anything that slips past them.

## 7. Uninstall

🇻🇳 *Gỡ cài — `uninstall.py` mặc định chỉ chạy thử (dry-run): in kế hoạch, không đụng gì; thêm `--yes` mới thực sự gỡ. Nó **giữ lại** file bạn đã sửa (không xoá việc của bạn). Bản tiếng Việt: [getting-started.vi.md](getting-started.vi.md).*

Removing the kit is symmetric to installing it, and **safe by default**: `uninstall.py` is a
**dry run unless you pass `--yes`**, so it shows you the plan before changing anything.

```bash
python uninstall.py /path/to/your/project          # dry run — prints the plan, changes nothing
python uninstall.py /path/to/your/project --yes    # apply: reverse the install
```

- **Dry run first.** With no `--yes` it only prints what *would* be removed, kept, or reverted —
  nothing on disk changes until you confirm.
- **It keeps files you edited.** A copied file you changed since install (its bytes no longer match
  the kit's) is **KEPT, not deleted** — uninstall never destroys your work.
- **It reverts settings precisely.** Only the hook commands install added are stripped from
  `.claude/settings.json`; any hooks you added yourself stay.
- **A clean install → uninstall leaves git clean.** On a fresh project you didn't edit, removing the
  kit restores the tree exactly. `uninstall.py` runs **from the kit folder** (it is never copied into
  your project).
- **Prefer to just talk to Claude Code?** Say *"uninstall agent-workbench from `<path-to-my-project>`"*
  — the agent (skill `awb-uninstall`) dry-runs it, relays the plan in plain language, asks you to
  confirm, then applies it.

## 8. Troubleshooting

🇻🇳 *Gỡ rối — vài vấp thường gặp: `python` không chạy trên Windows → cài lại; guard chưa bật → khởi động lại Claude Code; "guard của tôi bật chưa?" → chạy doctor (read-only). Bản tiếng Việt: [getting-started.vi.md](getting-started.vi.md).*

- **"`python` is not recognized" (Windows).** The hooks are wired with whatever interpreter resolved
  at install time. If `python` later stops resolving (a Store alias, a moved install), **re-run**
  `install.py <project> --merge-settings` — it re-detects a working `py`/`python3` and re-wires.
- **The guards don't seem to be on.** Restart Claude Code (or start a new session) after installing or
  re-wiring — hooks load at session start, not in the middle of a running session.
- **"Are my guards actually on?"** Run the doctor — it launches the wired guards and reports, writing
  nothing into your project:

```bash
python install.py /path/to/your/project --doctor   # from the kit folder (always works)
python tools/doctor.py                             # from inside your project (after install)
```

- **First-time setup needs the basics.** The kit assumes Python ≥ 3.10, Git, and — for the hooks and
  skills — Claude Code are already installed; it can't bootstrap those for you (see
  [section 0](#0-prerequisites)).
- **A commit was refused.** That's a guard doing its job, not your mistake — see
  [section 6](#6-when-a-commit-is-refused-and-who-fixes-it). Tell the agent "the commit was refused"
  and it diagnoses and fixes the cause.
