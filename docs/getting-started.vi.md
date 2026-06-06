# Bắt đầu (Getting Started)

> 🇻🇳 **Bản tiếng Việt (Vietnamese edition)** — hướng dẫn ~10 phút, viết cho người đọc Việt. Các
> **khối lệnh** bên dưới được giữ y hệt bản tiếng Anh [`getting-started.md`](getting-started.md)
> (một test CI canh để chúng không bao giờ lệch nhau); chỉ phần văn xung quanh là tiếng Việt.

<kbd>[🇬🇧 English](getting-started.md)</kbd> · <kbd>[README (VI)](README.vi.md)</kbd> · <kbd>[Thuật ngữ](README.vi.md#thuật-ngữ-nhanh)</kbd>

Một lượt đi ~10 phút: chạy thử các demo (mỗi cái vài giây), rồi gắn bộ tool vào dự án của bạn.

## 0. Yêu cầu

- **Python ≥ 3.10** (lõi tái dùng chỉ dùng stdlib; `pytest` chỉ dành cho bộ test — matrix CI là
  3.10 / 3.11 / 3.12).
- Git. Tuỳ chọn: [Claude Code](https://claude.com/claude-code) (hoặc agent khác) để dùng hooks và skills.

```bash
git clone https://github.com/doivamong/agent-workbench
cd agent-workbench
python -m pip install -r requirements.txt
```

**Tuỳ chọn thêm** — lõi (chỉ stdlib) không cần cái nào trong số này:

- Để chạy *các commit gate của chính repo này* tại máy (leak scan + invariants trong
  [`.pre-commit-config.yaml`](../.pre-commit-config.yaml)):

```bash
pip install pre-commit && pre-commit install
```

- Để chạy **dashboard web opt-in** — Flask + Jinja2 của nó là phụ thuộc runtime *duy nhất* của
  kit, cô lập trong `ui/web/` để lõi vẫn chỉ stdlib (xem [`ui/web/README.md`](../ui/web/README.md)):

```bash
pip install -r ui/web/requirements.txt
```

## 1. Xem nó chạy (mỗi lệnh vài giây)

```bash
python examples/secrets_demo.py             # encrypt/decrypt round-trip + tamper detection
python examples/hook_block_demo.py          # classifies safe vs dangerous shell commands
python examples/post_edit_simplify_demo.py  # the post-edit simplify-nudge classifier
python examples/invariant_demo.py           # the invariant gate catching rule violations
```

> **Bạn sẽ thấy:** `secrets_demo` in `<- round-trip OK`, rồi *từ chối* một file đã bị giả mạo;
> `hook_block_demo` kết thúc bằng `All classifications correct.`; `invariant_demo` báo `found 3
> violation(s)` cho các rule built-in và `found 1 violation(s)` cho một rule tự thêm của bạn. Không
> lệnh nào cần `pip` — đó chính là điểm mấu chốt: lõi chỉ dùng stdlib.

Rồi tự chứng minh các tool thực sự đáng tin:

```bash
python -m pytest -q                 # the test suite
python tools/leak_scan.py . --entropy --fail-on-find --respect-gitignore   # this repo scans itself: 0 findings (same flags as CI)
```

## 2. Cài vào dự án của bạn

> **Thích chỉ trò chuyện với Claude Code?** Trước hết clone agent-workbench và **mở thư mục đó**
> trong Claude Code, rồi nói: *"cài agent-workbench vào `<đường-dẫn-dự-án-của-tôi>` và xác nhận các
> guard đã bật."* Agent (skill `awb-install-and-verify`) chạy lệnh cài bên dưới nhắm vào dự án của
> bạn, rồi `install.py … --doctor` để chứng minh guard thực sự chạy — và nói thật cái gì được bảo vệ,
> cái gì không. Nó chạy **từ thư mục kit**, không phải từ trong dự án trống (ở đó chưa có tool).

```bash
python install.py /path/to/your/project --with-git-hook
python install.py /path/to/your/project --doctor   # then verify the wired guards actually fire
# --dry-run to preview; --force to overwrite existing files
```

Lệnh này chép hooks, skills, rules, tools, `secrets_guard`, và scaffold memory vào dự án của bạn;
tuỳ chọn cài một git pre-commit gate chống rò rỉ; rồi in đoạn `settings.json` bạn cần. Merge đoạn đó
vào `your-project/.claude/settings.json`.

## 3. Bạn có ngay những gì

Mở dự án bằng Claude Code (hoặc agent của bạn). Ngay lập tức:

- **Lệnh `Bash` nguy hiểm bị chặn** (force-push, `rm -rf /`, `DROP TABLE`, …) bởi một hook `PreToolUse`.
- **Prompt mơ hồ bị gắn cờ** để refine trước, bởi một hook `UserPromptSubmit`.
- **Commit làm rò rỉ secret bị từ chối** (nếu bạn dùng `--with-git-hook`).
- **Skills** dưới `.claude/skills/` và một **scaffold memory** dưới `memory/` (một khung mẫu tham
  chiếu — kho memory sống của bạn nằm ở đường dẫn per-project; xem "Biến thành của bạn" bên dưới).

## 4. Biến thành của bạn

- **Skills:** chép `.claude/skills/SKILL_TEMPLATE.md` và viết playbook cho workflow của bạn; giữ
  `.claude/skills/skill-registry.md` đồng bộ. Xem [`.claude/skills/README.md`](../.claude/skills/README.md).
- **Invariants:** thay `SAMPLE_INVARIANTS` trong `tools/invariants.py` bằng các rule "không được phá
  vỡ" thật của dự án. Bật hook invariants trong `.pre-commit-config.yaml`.
- **Leak scanner:** giữ một deny-list riêng (gitignored) gồm các định danh của dự án, rồi chạy
  `python tools/leak_scan.py . --denylist your-denylist.txt` để vet các bản export.
- **Memory — 6 bước** (thư mục `memory/` được chép chỉ là khung mẫu; *recall sống đọc một thư mục
  KHÁC*, đây là chỗ hay nhầm nhất):
  1. **Đừng** sửa `memory/` của repo này cho recall sống — nó chứa **fact ví dụ để bạn thay**.
  2. Tìm thư mục sống của bạn: Claude Code (v2.1.59+) tự nạp `MEMORY.md` từ đường dẫn per-project
     `~/.claude/projects/<id>/memory/` (hoặc nơi `autoMemoryDirectory` trỏ tới).
  3. Thêm một fact thật ở đó dưới dạng file `kebab-name.md`.
  4. Thêm một dòng link tới nó từ index `MEMORY.md` của thư mục đó.
  5. Chạy `python tools/memory_recall_doctor.py` để kiểm tra wiring.
  6. Xác nhận agent recall được nó ở phiên sau. Thiết kế đầy đủ + lý do:
     [`memory/README.md`](../memory/README.md) · [`memory-governance.md`](memory-governance.md).
- **Rule dự án:** chỉnh [`../CLAUDE.md`](../CLAUDE.md) / [`../AGENTS.md`](../AGENTS.md) theo golden
  rules của dự án bạn.

## 5. CI

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) kèm sẵn chạy leak scan, invariants, và
tests mỗi push/PR — kit tự gate bằng chính tool của nó. Dùng lại mẫu này cho dự án bạn.
