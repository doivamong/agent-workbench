#!/usr/bin/env python3
"""ui/web/i18n.py — the EN/VI string catalog for the opt-in web dashboard.

One source of truth for every user-facing string in ``ui/web`` (the read-only dashboard,
its HTMX fragments, and the ``/admin`` action surface). The dashboard renders **one** language
at a time (server-side, chosen per request) — there is no client-side dictionary and no doubled
DOM, so the two languages can never drift out of sync on screen.

Language resolution (see ``app._resolve`` / ``resolve_lang`` here): an explicit ``?lang=`` query
wins, else the ``awb_lang`` cookie, else the default (**Vietnamese**). The cookie is what keeps
HTMX fragments — which do not resend ``?lang`` — in the same language as the page.

This module is **stdlib-only** (it is just data + tiny helpers, no Flask import), so it could be
lifted into the stdlib core later if ``ui/kit_status`` ever grows a ``--lang`` flag. The web app
(``app.py``) and the admin blueprint (``admin.py``) both import it.

Conventions:
  * UI template strings live in ``_UI``; some carry inline HTML (``<span class="mono">`` …) and
    are rendered with Jinja's ``|safe``. Strings with a runtime value use ``{name}`` placeholders
    and are filled with ``str.format`` in the template — keeping word order correct per language
    instead of gluing translated fragments around a number.
  * Server-rendered ``/admin`` result messages live in ``_ADMIN`` (filled with ``.format`` in
    ``admin.py``).
  * The single JS string (a Chart.js axis label) lives in ``_JS`` and is shipped to the page as a
    small embedded JSON blob.
  * **The Vietnamese values are verbatim the strings the templates shipped before i18n** — the
    default language is Vietnamese, so the existing tests (which assert the VI render) stay green
    and the VI experience is byte-identical.
  * The EN/VI switcher's option labels (``VI`` / ``EN`` in ``_lang_switch.html.jinja``) are
    deliberately NOT in this catalog: they are language-CODE identifiers, identical in both
    languages and not translatable, so cataloging them would be empty ceremony.
"""
from __future__ import annotations

LANGS = ("vi", "en")
DEFAULT_LANG = "vi"


def normalize_lang(raw: str | None) -> str:
    """A single language code, validated against the whitelist (else the default)."""
    return raw if raw in LANGS else DEFAULT_LANG


def resolve_lang(arg_lang: str | None = None, cookie_lang: str | None = None) -> str:
    """Pick the language: an explicit ``?lang=`` query wins, else the cookie, else the default.

    Pure (takes plain strings, no Flask import) so both ``app.py`` and ``admin.py`` can share it
    without a circular import."""
    if arg_lang in LANGS:
        return arg_lang
    if cookie_lang in LANGS:
        return cookie_lang
    return DEFAULT_LANG


# Tier display labels (the doughnut chips + the tier filter). The raw tier *ids*
# (workflow/guard/…) stay English in the skills-table "Loại/Tier" column; these are the
# human labels. EN keeps the registry's own words.
TIER_LABELS = {
    "vi": {"workflow": "quy trình", "guard": "bảo vệ", "feature": "tính năng",
           "audit": "kiểm toán", "meta": "điều phối"},
    "en": {"workflow": "workflow", "guard": "guard", "feature": "feature",
           "audit": "audit", "meta": "meta"},
}
FILTER_ALL = {"vi": "Tất cả", "en": "All"}

# The one string used only inside dashboard.js (the timeseries axis label).
_JS = {
    "vi": {"chart_axis": "Lượt gọi tên/ngày"},
    "en": {"chart_axis": "Name-calls/day"},
}


# --------------------------------------------------------------------------- #
# UI template strings (the read-only dashboard + /admin templates)
# --------------------------------------------------------------------------- #
_UI = {
    "vi": {
        # --- shared chrome ---
        "lang_aria": "Ngôn ngữ",
        "pill_local": "CỤC BỘ",
        "pill_branch": "Nhánh",
        "pill_commit": "Commit",
        # --- dashboard shell (dashboard.html.jinja) ---
        "meta_title": "Agent Workbench — Bảng điều khiển trạng thái kit",
        "skip_to_content": "Bỏ qua tới nội dung chính",
        "brand_eyebrow": "Agent Workbench · trạng thái kit",
        "dash_h1": "Bảng điều khiển kit",
        "admin_login_link": "Đăng nhập admin",
        "topbar_sub": ('Ảnh chụp cục bộ, đọc trực tiếp từ <span class="mono">generator.gather()</span> — '
                       "{n_skills} skill, {n_hooks} hook đã nối."),
        "controls_group_aria": "Tuỳ chọn cửa sổ thời gian",
        "control_window": "Cửa sổ",
        "days_unit": "ngày",
        "btn_refresh": "Làm mới",
        "controls_hint": "Ảnh chụp tại chỗ — bấm để đọc lại từ đĩa",
        "footer": "Agent Workbench · bảng điều khiển trạng thái kit · ảnh chụp cục bộ",
        # --- honesty banners (_body.html.jinja) ---
        "banner_notwired": ('<strong>Telemetry chưa bật.</strong> '
            "Số lượt gọi tên skill là <strong>chưa đo</strong>, không phải “chết”. "
            'Bật bằng cách thêm <span class="mono">skill_usage_logger</span> vào '
            '<span class="mono">.claude/settings.json</span>.'),
        "banner_empty": ('<strong>Telemetry vừa bật — chưa có dữ liệu.</strong> '
            "Logger đã nối nhưng log còn trống; skill vẫn là <strong>chưa đo</strong>, "
            "không phải “chết”. Dữ liệu tích lũy từ các phiên sau."),
        "banner_measured": ('<strong style="color:var(--text-strong)">Đang đo theo tên trong prompt.</strong> '
            'Chỉ số đếm lượt người dùng <strong style="color:var(--text-strong)">gõ tên</strong> skill '
            '(<span class="mono">/tên</span> hoặc nhắc tên). Skill model tự gọi — nhất là skill bảo vệ/guard '
            '(output-guard, config-guard) — <strong style="color:var(--text-strong)">không tính</strong> '
            "ở đây; 0 nghĩa là chưa ai gõ tên trong cửa sổ này, không phải skill hỏng hay vô dụng."),
        # --- KPI strip ---
        "kpibar_aria": "Chỉ số tóm tắt",
        "kpi_skills": "Skill",
        "kpi_skills_sub_measured": "{dead} chưa ai gọi tên",
        "kpi_skills_sub_unmeasured": "chưa đo lượt gọi tên",
        "kpi_namecalls": "Lượt gọi tên · {days} ngày",
        "unit_calls": "lượt",
        "kpi_namecalls_unmeasured": "chưa đo",
        "kpi_namecalls_sub_measured": "trung bình {avg}/ngày",
        "kpi_namecalls_sub_unmeasured": "bật telemetry để đo",
        "kpi_tools": "Công cụ",
        "kpi_tools_sub_missing": "thiếu {n}",
        "kpi_tools_sub_ok": "đủ bộ",
        "kpi_hooks": "Hook đã nối",
        "kpi_hooks_sub": "{n} loại sự kiện",
        "kpi_mem": "Bộ nhớ đã dùng",
        "kpi_mem_sub_present": "{facts} fact",
        "kpi_mem_sub_absent": "không có MEMORY.md",
        # --- telemetry panel ---
        "panel_telemetry_eyebrow": "Telemetry",
        "panel_telemetry_h2": "Lượt gọi tên skill",
        "badge_total": "tổng",
        "badge_unmeasured": "chưa đo",
        "chart_ts_aria": "Biểu đồ đường: số lượt gọi tên skill mỗi ngày trong {days} ngày",
        "ts_foot": ('Dữ liệu thật từ <span class="mono">.claude/.logs/skill_usage.jsonl</span>, '
                    "không nội suy."),
        "empty_ts_title": "Chưa có dữ liệu telemetry",
        "empty_ts_wired": ("Logger đã nối nhưng log còn trống — biểu đồ sẽ hiện khi có dữ liệu "
                           "từ các phiên sau."),
        "empty_ts_notwired": ('Nối <span class="mono">skill_usage_logger</span> vào '
            '<span class="mono">UserPromptSubmit</span> trong settings.json để bắt đầu đo.'),
        # --- tiers panel ---
        "panel_tiers_eyebrow": "Hệ skill",
        "panel_tiers_h2": "Phân bố loại",
        "chart_tiers_aria": "Biểu đồ tròn phân bố skill theo loại",
        # --- skills panel ---
        "panel_skills_eyebrow": "Hệ skill",
        "panel_skills_h2": "Skill &amp; trạng thái",
        "filter_tier": "Lọc loại",
        "badge_n_skills": "skill",
        "badge_dead": "chưa ai gọi tên",
        "skills_region_aria": "Bảng skill và trạng thái — cuộn ngang trên màn hình nhỏ",
        # --- skills table (_skills.html.jinja) ---
        "th_skill": "Skill",
        "th_tier": "Loại",
        "th_namecalls": "Lượt gọi tên",
        "th_signal": "Tín hiệu",
        "badge_guard_title": "Skill này do model tự gọi, không gõ tên — 0 ở đây là bình thường.",
        "badge_guard": "tự gọi · không đo qua prompt",
        "badge_dead_title": ("Không có prompt nào gọi tên skill này trong cửa sổ đo. Tín hiệu để "
                             "xem lại (đặt tên khó tìm? trùng? thừa?), chưa phải kết luận chết."),
        "badge_named": "đã gọi tên",
        "skills_empty_tier": "Không có skill thuộc loại này.",
        # --- tools panel ---
        "panel_tools_eyebrow": "Bộ công cụ",
        "panel_tools_h2": "Công cụ có mặt",
        "tools_present_unit": "có mặt",
        "tools_foot_missing": "Còn thiếu {n} công cụ:",
        "tools_foot_ok": 'Tất cả công cụ kit có mặt trong <span class="mono">tools/</span>.',
        # --- memory panel ---
        "panel_mem_eyebrow": "Hệ bộ nhớ",
        "panel_mem_h2": "Ngân sách bộ nhớ",
        "badge_mem_used": "đã dùng",
        "mem_meter_aria": "Đã dùng {pct}% ngân sách bộ nhớ",
        "mem_foot_main": "{facts} fact · {dangling} liên kết hỏng",
        "mem_foot_over": " · trên ngưỡng 75%, gom/cắt fact trước khi thêm",
        "empty_mem_title": "Không tìm thấy MEMORY.md",
        "empty_mem_msg": "Hệ bộ nhớ chưa được khởi tạo trong dự án này.",
        # --- hooks panel ---
        "panel_hooks_eyebrow": "Hook an toàn",
        "panel_hooks_h2": "Hook đã nối",
        "badge_hooks": "hook",
        "hooks_empty": "chưa nối hook nào",
        # --- admin shell (admin.html.jinja) ---
        "admin_meta_title": "Agent Workbench — /admin · điều khiển kit",
        "admin_skip_to_actions": "Bỏ qua tới các thao tác",
        "admin_eyebrow": "Agent Workbench · /admin",
        "admin_h1": "Điều khiển kit",
        "admin_back_dashboard": "← Bảng điều khiển (chỉ đọc)",
        "admin_logout": "Đăng xuất",
        "admin_banner": ('<strong style="color:var(--accent-fg)">/admin đã đăng nhập.</strong> '
            "Đây là cổng <strong>HTTP</strong> — mật khẩu và cookie phiên đi <strong>cleartext</strong> "
            "trên LAN, có thể bị nghe lén. Chỉ bật trong <strong>mạng tin cậy</strong>, không hướng ra "
            "Internet. CSRF chặn giả mạo từ trình duyệt khác nguồn."),
        "admin_restart_eyebrow": "Tiến trình",
        "admin_restart_h2": "Khởi động lại",
        "admin_restart_foot": "Dừng tiến trình dashboard này (qua pidfile) và sinh một tiến trình mới — tách rời.",
        "admin_restart_confirm": "Khởi động lại dashboard? Trang sẽ tự kết nối lại.",
        "admin_restart_btn": "Khởi động lại dashboard",
        "admin_snap_eyebrow": "An toàn",
        "admin_snap_h2": "Chụp ảnh cây",
        "admin_snap_foot": 'Lưu ảnh chụp cây làm việc (tôn trọng .gitignore) vào <span class="mono">.ops/snapshots/</span>.',
        "admin_snap_btn": "Chụp ảnh ngay",
        "admin_pack_eyebrow": "Phát hành",
        "admin_pack_h2": "Đóng gói",
        "admin_pack_foot": 'Đóng gói đúng payload <span class="mono">install.py</span> thành zip có manifest sha256.',
        "admin_pack_btn": "Đóng gói bản phát hành",
        "admin_verify_eyebrow": "Toàn vẹn",
        "admin_verify_h2": "Kiểm tra bản phát hành",
        "admin_verify_label": "Chọn bản phát hành (do máy chủ liệt kê)",
        "admin_verify_btn": "Kiểm tra sha256 vs manifest",
        "admin_verify_empty": 'Chưa có bản phát hành nào trong <span class="mono">.ops/releases/</span> — đóng gói một bản trước.',
        "admin_restore_eyebrow": "Khôi phục (có bảo vệ)",
        "admin_restore_h2": "Khôi phục cây từ ảnh chụp",
        "admin_restore_dirty_badge": "cây chưa commit",
        "admin_restore_foot": ("Bước 1 — xem trước (dry-run) sinh plan-hash; bước 2 — khôi phục re-kiểm "
                               "hash (chống TOCTOU), tự sao lưu trước, từ chối cây bẩn trừ khi cho phép."),
        "admin_restore_label": "Chọn ảnh chụp (do máy chủ liệt kê)",
        "admin_restore_btn": "Xem trước khôi phục →",
        "admin_restore_empty": 'Chưa có ảnh chụp nào trong <span class="mono">.ops/snapshots/</span> — chụp một ảnh trước.',
        "admin_sys_eyebrow": "Hệ thống",
        "admin_sys_h2": "Mạng LAN &amp; tự khởi động",
        "admin_sys_bind": "Bind hiện hành:",
        "admin_sys_lan_default": "mặc định LAN:",
        "admin_sys_on": "BẬT",
        "admin_sys_off": "TẮT",
        "admin_sys_autostart": "tự khởi động:",
        "admin_sys_as_on": "đã bật",
        "admin_sys_as_err": "lỗi",
        "admin_sys_as_off": "chưa bật",
        "admin_sys_phone": "Mở từ điện thoại cùng Wi-Fi:",
        "admin_sys_firewall_hint": ('Mở firewall (cần quyền admin — chạy lệnh này trong PowerShell '
            "<em>Run as administrator</em>, hoặc bấm đúp <span class=\"mono\">win/lan_on.bat</span>):"),
        "admin_sys_actions_hint": ("Thao tác (LAN bật/tắt không cần admin; firewall &amp; tự khởi động "
                                   "cần admin — sẽ báo nếu thiếu quyền):"),
        "admin_lan_enable_label": "Bật mặc định LAN",
        "admin_lan_enable_confirm": "Đặt AWB_DASHBOARD_HOST=0.0.0.0 (setx) và áp dụng. Khởi động lại để có hiệu lực?",
        "admin_lan_disable_label": "Tắt mặc định LAN",
        "admin_lan_disable_confirm": "Quay về localhost-only?",
        "admin_fw_open_label": "Mở firewall LAN",
        "admin_fw_open_confirm": "Tạo rule inbound (cần quyền admin)?",
        "admin_as_enable_label": "Bật tự khởi động",
        "admin_as_enable_confirm": "Tạo tác vụ chạy lúc đăng nhập (có thể cần admin)?",
        "admin_as_disable_label": "Tắt tự khởi động",
        "admin_as_disable_confirm": "Xoá tác vụ tự khởi động?",
        "admin_pw_eyebrow": "Bảo mật",
        "admin_pw_h2": "Đổi mật khẩu admin",
        "admin_pw_foot": ('Mật khẩu mới lưu bền vào <span class="mono">.ops/admin.hash</span> '
            "(không commit) và thay mật khẩu env ngay — không cần khởi động lại. Tối thiểu 8 ký tự. "
            "Lưu ý: trên HTTP/LAN mật khẩu đi cleartext — chỉ đổi trong mạng tin cậy."),
        "admin_pw_old": "Mật khẩu cũ",
        "admin_pw_new": "Mật khẩu mới (≥8 ký tự)",
        "admin_pw_btn": "Đổi mật khẩu",
        "admin_footer": ('Agent Workbench · /admin · điều khiển cục bộ · mọi thao tác ghi nhật ký vào '
                         '<span class="mono">.ops/ops.log</span>'),
        # --- admin login (admin_login.html.jinja) ---
        "login_meta_title": "Agent Workbench — /admin · đăng nhập",
        "login_title_no_password": "Chưa bật admin",
        "login_title": "Đăng nhập",
        "login_inert_lead": ("Khu vực điều khiển kit hiện <strong>chưa kích hoạt</strong>: chưa đặt "
                             "mật khẩu quản trị, nên mọi thao tác đều bị từ chối và không thể đăng nhập."),
        "login_inert_banner": ('Để bật admin, đặt biến môi trường <span class="mono">AWB_ADMIN_PASSWORD</span> '
            'rồi <strong>khởi động lại</strong> dashboard. Sau lần đặt đầu tiên, có thể đổi mật khẩu '
            'ngay trong giao diện <span class="mono">/admin</span> (không cần khởi động lại).'),
        "login_inert_example_label": "Ví dụ (PowerShell)",
        "login_inert_example_cmd": "$env:AWB_ADMIN_PASSWORD = 'mật-khẩu-mạnh'; python ui/web/app.py",
        "login_back_readonly": "← Về bảng điều khiển (chỉ đọc)",
        "login_lead": "Khu vực điều khiển kit. Nhập mật khẩu quản trị để tiếp tục.",
        "login_password_label": "Mật khẩu",
        "login_btn": "Đăng nhập",
        "login_back_readonly2": "← Bảng điều khiển (chỉ đọc)",
        "login_change_pw_hint": 'Đổi mật khẩu? Đăng nhập rồi vào <span class="mono">/admin</span>',
        "login_forgot_summary": "Quên mật khẩu?",
        "login_forgot_p1": ("Không có nút đặt lại qua web — <strong>có chủ đích</strong>: bất kỳ ai "
            "trong LAN cũng sẽ chiếm được admin. Khôi phục cần quyền truy cập máy chủ (đó mới là bằng "
            "chứng bạn là chủ). Trên máy chạy dashboard:"),
        "login_forgot_p2": ('1) <strong>Dễ nhất</strong> — đặt mật khẩu mới ngay (không cần khởi động '
            'lại): bấm đúp <span class="mono">ops/win/set_password.bat</span>, hoặc chạy '
            '<span class="mono">python ui/web/set_password.py</span>.'),
        "login_forgot_p3": ('2) Hoặc xoá mật khẩu đã lưu rồi <strong>khởi động lại</strong>: '
            '<span class="mono">Remove-Item .ops/admin.hash</span> — quay về mật khẩu env (nếu có), '
            "hoặc về trạng thái chưa bật."),
        "login_forgot_p4": ('3) Hoặc đặt qua env rồi <strong>khởi động lại</strong>: '
            "<span class=\"mono\">$env:AWB_ADMIN_PASSWORD = 'mật-khẩu-mới'; python ui/web/app.py</span>"),
        "login_note": ("⚠️ Đây là cổng HTTP trên LAN — mật khẩu có thể bị nghe lén trong mạng. "
                       "Chỉ bật trong mạng tin cậy, không hướng ra Internet."),
        # --- restore preview partial (_admin_restore_plan.html.jinja) ---
        "restore_preview_head": "Xem trước khôi phục",
        "restore_plan_msg": ("Sẽ <strong>tạo {create}</strong> · <strong>sửa {modify}</strong> · "
            "giữ nguyên {unchanged} (tổng {total} tệp trong ảnh chụp). "
            "Khôi phục là <em>lớp phủ</em>: chỉ ghi tệp trong ảnh chụp, không xoá tệp mới."),
        "restore_dirty_warn": ('⚠ Cây làm việc đang có thay đổi <strong>chưa commit</strong> — '
                               "phải tick “allow_dirty” để ghi đè."),
        "restore_confirm": "Khôi phục sẽ ghi đè {modify} tệp (đã tự sao lưu trước). Tiếp tục?",
        "restore_check_label": 'Ghi đè ngay cả khi cây chưa commit <span class="mono">(allow_dirty)</span>',
        "restore_btn": "Khôi phục {modify} tệp · tự sao lưu trước",
        "restore_hint": ('plan-hash <span class="mono">{hash}…</span> — '
                         "nếu cây đổi trước khi bấm, thao tác sẽ bị huỷ (không ghi gì)."),
    },
    "en": {
        # --- shared chrome ---
        "lang_aria": "Language",
        "pill_local": "LOCAL",
        "pill_branch": "Branch",
        "pill_commit": "Commit",
        # --- dashboard shell ---
        "meta_title": "Agent Workbench — Kit status dashboard",
        "skip_to_content": "Skip to main content",
        "brand_eyebrow": "Agent Workbench · kit status",
        "dash_h1": "Kit dashboard",
        "admin_login_link": "Admin login",
        "topbar_sub": ('Local snapshot, read straight from <span class="mono">generator.gather()</span> — '
                       "{n_skills} skills, {n_hooks} hooks wired."),
        "controls_group_aria": "Time-window options",
        "control_window": "Window",
        "days_unit": "days",
        "btn_refresh": "Refresh",
        "controls_hint": "In-place snapshot — click to re-read from disk",
        "footer": "Agent Workbench · kit status dashboard · local snapshot",
        # --- honesty banners ---
        "banner_notwired": ('<strong>Telemetry is off.</strong> '
            'Skill name-call counts are <strong>not measured</strong>, not “dead”. '
            'Turn it on by adding <span class="mono">skill_usage_logger</span> to '
            '<span class="mono">.claude/settings.json</span>.'),
        "banner_empty": ('<strong>Telemetry just enabled — no data yet.</strong> '
            "The logger is wired but the log is still empty; skills are still <strong>not measured</strong>, "
            "not “dead”. Data accumulates over later sessions."),
        "banner_measured": ('<strong style="color:var(--text-strong)">Measuring by name typed in the prompt.</strong> '
            'The metric counts how often a user <strong style="color:var(--text-strong)">types the name</strong> of a skill '
            '(<span class="mono">/name</span> or mentioning it). Skills the model auto-fires — especially guards '
            '(output-guard, config-guard) — <strong style="color:var(--text-strong)">are not counted</strong> '
            "here; 0 means nobody typed the name in this window, not that the skill is broken or useless."),
        # --- KPI strip ---
        "kpibar_aria": "Summary metrics",
        "kpi_skills": "Skills",
        "kpi_skills_sub_measured": "{dead} never name-called",
        "kpi_skills_sub_unmeasured": "name-calls not measured",
        "kpi_namecalls": "Name-calls · {days} days",
        "unit_calls": "calls",
        "kpi_namecalls_unmeasured": "not measured",
        "kpi_namecalls_sub_measured": "avg {avg}/day",
        "kpi_namecalls_sub_unmeasured": "enable telemetry to measure",
        "kpi_tools": "Tools",
        "kpi_tools_sub_missing": "{n} missing",
        "kpi_tools_sub_ok": "complete",
        "kpi_hooks": "Hooks wired",
        "kpi_hooks_sub": "{n} event types",
        "kpi_mem": "Memory used",
        "kpi_mem_sub_present": "{facts} facts",
        "kpi_mem_sub_absent": "no MEMORY.md",
        # --- telemetry panel ---
        "panel_telemetry_eyebrow": "Telemetry",
        "panel_telemetry_h2": "Skill name-calls",
        "badge_total": "total",
        "badge_unmeasured": "not measured",
        "chart_ts_aria": "Line chart: skill name-calls per day over {days} days",
        "ts_foot": ('Real data from <span class="mono">.claude/.logs/skill_usage.jsonl</span>, '
                    "not interpolated."),
        "empty_ts_title": "No telemetry data yet",
        "empty_ts_wired": ("The logger is wired but the log is empty — the chart appears once later "
                           "sessions produce data."),
        "empty_ts_notwired": ('Wire <span class="mono">skill_usage_logger</span> into '
            '<span class="mono">UserPromptSubmit</span> in settings.json to start measuring.'),
        # --- tiers panel ---
        "panel_tiers_eyebrow": "Skill system",
        "panel_tiers_h2": "Tier distribution",
        "chart_tiers_aria": "Doughnut chart: skills by tier",
        # --- skills panel ---
        "panel_skills_eyebrow": "Skill system",
        "panel_skills_h2": "Skills &amp; status",
        "filter_tier": "Filter tier",
        "badge_n_skills": "skills",
        "badge_dead": "never name-called",
        "skills_region_aria": "Skills and status table — scroll horizontally on small screens",
        # --- skills table ---
        "th_skill": "Skill",
        "th_tier": "Tier",
        "th_namecalls": "Name-calls",
        "th_signal": "Signal",
        "badge_guard_title": "This skill is auto-fired by the model, not typed by name — a 0 here is normal.",
        "badge_guard": "auto-fired · not measured via prompt",
        "badge_dead_title": ("No prompt named this skill in the measured window. A signal to review "
                             "(hard-to-find name? duplicate? redundant?), not a verdict of dead."),
        "badge_named": "name-called",
        "skills_empty_tier": "No skills in this tier.",
        # --- tools panel ---
        "panel_tools_eyebrow": "Toolset",
        "panel_tools_h2": "Tools present",
        "tools_present_unit": "present",
        "tools_foot_missing": "{n} tools missing:",
        "tools_foot_ok": 'All kit tools are present in <span class="mono">tools/</span>.',
        # --- memory panel ---
        "panel_mem_eyebrow": "Memory system",
        "panel_mem_h2": "Memory budget",
        "badge_mem_used": "used",
        "mem_meter_aria": "Used {pct}% of the memory budget",
        "mem_foot_main": "{facts} facts · {dangling} broken links",
        "mem_foot_over": " · over the 75% threshold, consolidate/trim facts before adding",
        "empty_mem_title": "MEMORY.md not found",
        "empty_mem_msg": "The memory system isn't initialised in this project.",
        # --- hooks panel ---
        "panel_hooks_eyebrow": "Safety hooks",
        "panel_hooks_h2": "Hooks wired",
        "badge_hooks": "hooks",
        "hooks_empty": "no hooks wired",
        # --- admin shell ---
        "admin_meta_title": "Agent Workbench — /admin · kit control",
        "admin_skip_to_actions": "Skip to actions",
        "admin_eyebrow": "Agent Workbench · /admin",
        "admin_h1": "Kit control",
        "admin_back_dashboard": "← Dashboard (read-only)",
        "admin_logout": "Log out",
        "admin_banner": ('<strong style="color:var(--accent-fg)">/admin is logged in.</strong> '
            "This is an <strong>HTTP</strong> endpoint — the password and session cookie travel "
            "<strong>cleartext</strong> on the LAN and can be sniffed. Only enable it on a "
            "<strong>trusted network</strong>, never Internet-facing. CSRF blocks forgery from a "
            "cross-origin browser."),
        "admin_restart_eyebrow": "Process",
        "admin_restart_h2": "Restart",
        "admin_restart_foot": "Stop this dashboard process (via the pidfile) and spawn a new one — detached.",
        "admin_restart_confirm": "Restart the dashboard? The page will reconnect automatically.",
        "admin_restart_btn": "Restart dashboard",
        "admin_snap_eyebrow": "Safety",
        "admin_snap_h2": "Snapshot tree",
        "admin_snap_foot": 'Save a working-tree snapshot (respects .gitignore) to <span class="mono">.ops/snapshots/</span>.',
        "admin_snap_btn": "Snapshot now",
        "admin_pack_eyebrow": "Release",
        "admin_pack_h2": "Pack",
        "admin_pack_foot": 'Pack exactly the <span class="mono">install.py</span> payload into a zip with a sha256 manifest.',
        "admin_pack_btn": "Pack a release",
        "admin_verify_eyebrow": "Integrity",
        "admin_verify_h2": "Verify a release",
        "admin_verify_label": "Choose a release (server-listed)",
        "admin_verify_btn": "Verify sha256 vs manifest",
        "admin_verify_empty": 'No releases in <span class="mono">.ops/releases/</span> yet — pack one first.',
        "admin_restore_eyebrow": "Restore (guarded)",
        "admin_restore_h2": "Restore tree from a snapshot",
        "admin_restore_dirty_badge": "uncommitted tree",
        "admin_restore_foot": ("Step 1 — preview (dry-run) produces a plan-hash; step 2 — restore re-checks "
                               "the hash (anti-TOCTOU), auto-backs-up first, refuses a dirty tree unless allowed."),
        "admin_restore_label": "Choose a snapshot (server-listed)",
        "admin_restore_btn": "Preview restore →",
        "admin_restore_empty": 'No snapshots in <span class="mono">.ops/snapshots/</span> yet — take one first.',
        "admin_sys_eyebrow": "System",
        "admin_sys_h2": "LAN &amp; autostart",
        "admin_sys_bind": "Current bind:",
        "admin_sys_lan_default": "LAN default:",
        "admin_sys_on": "ON",
        "admin_sys_off": "OFF",
        "admin_sys_autostart": "autostart:",
        "admin_sys_as_on": "enabled",
        "admin_sys_as_err": "error",
        "admin_sys_as_off": "not enabled",
        "admin_sys_phone": "Open from a phone on the same Wi-Fi:",
        "admin_sys_firewall_hint": ('Open the firewall (needs admin — run this in PowerShell '
            "<em>Run as administrator</em>, or double-click <span class=\"mono\">win/lan_on.bat</span>):"),
        "admin_sys_actions_hint": ("Actions (LAN on/off needs no admin; firewall &amp; autostart need admin "
                                   "— you'll be told if permission is missing):"),
        "admin_lan_enable_label": "Enable LAN default",
        "admin_lan_enable_confirm": "Set AWB_DASHBOARD_HOST=0.0.0.0 (setx) and apply. Restart to take effect?",
        "admin_lan_disable_label": "Disable LAN default",
        "admin_lan_disable_confirm": "Back to localhost-only?",
        "admin_fw_open_label": "Open LAN firewall",
        "admin_fw_open_confirm": "Create an inbound rule (needs admin)?",
        "admin_as_enable_label": "Enable autostart",
        "admin_as_enable_confirm": "Create a task that runs at login (may need admin)?",
        "admin_as_disable_label": "Disable autostart",
        "admin_as_disable_confirm": "Remove the autostart task?",
        "admin_pw_eyebrow": "Security",
        "admin_pw_h2": "Change admin password",
        "admin_pw_foot": ('The new password is persisted to <span class="mono">.ops/admin.hash</span> '
            "(never committed) and replaces the env password immediately — no restart. Minimum 8 characters. "
            "Note: over HTTP/LAN the password travels cleartext — only change it on a trusted network."),
        "admin_pw_old": "Old password",
        "admin_pw_new": "New password (≥8 chars)",
        "admin_pw_btn": "Change password",
        "admin_footer": ('Agent Workbench · /admin · local control · every action logged to '
                         '<span class="mono">.ops/ops.log</span>'),
        # --- admin login ---
        "login_meta_title": "Agent Workbench — /admin · login",
        "login_title_no_password": "Admin not enabled",
        "login_title": "Log in",
        "login_inert_lead": ("The kit control area is <strong>not active</strong>: no admin password is "
                             "set, so every action is refused and login is impossible."),
        "login_inert_banner": ('To enable admin, set the environment variable <span class="mono">AWB_ADMIN_PASSWORD</span> '
            'then <strong>restart</strong> the dashboard. After the first time, you can change the password '
            'right in the <span class="mono">/admin</span> UI (no restart needed).'),
        "login_inert_example_label": "Example (PowerShell)",
        "login_inert_example_cmd": "$env:AWB_ADMIN_PASSWORD = 'strong-passphrase'; python ui/web/app.py",
        "login_back_readonly": "← Back to dashboard (read-only)",
        "login_lead": "Kit control area. Enter the admin password to continue.",
        "login_password_label": "Password",
        "login_btn": "Log in",
        "login_back_readonly2": "← Dashboard (read-only)",
        "login_change_pw_hint": 'Change password? Log in then go to <span class="mono">/admin</span>',
        "login_forgot_summary": "Forgot password?",
        "login_forgot_p1": ("There is no web reset button — <strong>by design</strong>: anyone on the LAN "
            "could otherwise seize admin. Recovery needs host access (that is what proves you are the "
            "owner). On the machine running the dashboard:"),
        "login_forgot_p2": ('1) <strong>Easiest</strong> — set a new password right now (no restart): '
            'double-click <span class="mono">ops/win/set_password.bat</span>, or run '
            '<span class="mono">python ui/web/set_password.py</span>.'),
        "login_forgot_p3": ('2) Or delete the stored password and <strong>restart</strong>: '
            '<span class="mono">Remove-Item .ops/admin.hash</span> — falls back to the env password (if any), '
            "or to the not-enabled state."),
        "login_forgot_p4": ('3) Or set it via the env and <strong>restart</strong>: '
            "<span class=\"mono\">$env:AWB_ADMIN_PASSWORD = 'new-passphrase'; python ui/web/app.py</span>"),
        "login_note": ("⚠️ This is an HTTP endpoint on the LAN — the password can be sniffed on the network. "
                       "Only enable it on a trusted network, never Internet-facing."),
        # --- restore preview partial ---
        "restore_preview_head": "Restore preview",
        "restore_plan_msg": ("Will <strong>create {create}</strong> · <strong>modify {modify}</strong> · "
            "leave {unchanged} unchanged ({total} files total in the snapshot). "
            "Restore is an <em>overlay</em>: it only writes files in the snapshot, never deletes new files."),
        "restore_dirty_warn": ('⚠ The working tree has <strong>uncommitted</strong> changes — '
                               "you must tick “allow_dirty” to overwrite."),
        "restore_confirm": "Restore will overwrite {modify} files (auto-backed-up first). Continue?",
        "restore_check_label": 'Overwrite even if the tree is uncommitted <span class="mono">(allow_dirty)</span>',
        "restore_btn": "Restore {modify} files · auto-backup first",
        "restore_hint": ('plan-hash <span class="mono">{hash}…</span> — '
                         "if the tree changes before you click, the action aborts (nothing written)."),
    },
}


# --------------------------------------------------------------------------- #
# /admin server-rendered result messages (filled with .format in admin.py)
# --------------------------------------------------------------------------- #
_ADMIN = {
    "vi": {
        "err_title": "Lỗi",
        "login_locked": "Tạm khoá do nhập sai quá nhiều lần. Thử lại sau.",
        "login_wrong": "Sai mật khẩu.",
        "pw_denied_title": "Bị từ chối",
        "pw_wrong_old": "Mật khẩu cũ không đúng.",
        "pw_too_short": "Mật khẩu mới phải tối thiểu {min} ký tự.",
        "pw_changed_title": "Đã đổi mật khẩu",
        "pw_changed_msg": "Mật khẩu admin đã đổi. Các đăng nhập mới dùng mật khẩu này.",
        "restart_err": "Không khởi động lại được: {exc}",
        "restart_title": "Đang khởi động lại",
        "restart_msg": ("Đã sinh tiến trình khởi động lại tách rời (PID {pid}). "
                        "Trang sẽ tự kết nối lại khi dashboard sống lại."),
        "snap_err": "Chụp ảnh thất bại (mã {rc}). {err}",
        "snap_title": "Đã chụp ảnh cây làm việc",
        "snap_msg": "Ảnh chụp đã lưu: {name}",
        "pack_err": "Đóng gói thất bại (mã {rc}). {err}",
        "pack_title": "Đã đóng gói bản phát hành",
        "pack_msg": "Bản phát hành: {name} ({files} tệp payload).",
        "verify_err": "Kiểm tra thất bại (mã {rc}). {err}",
        "verify_ok_title": "Kiểm tra toàn vẹn",
        "verify_ok_msg": "Bản phát hành {name} nguyên vẹn — mọi sha256 khớp manifest.",
        "verify_bad_title": "Phát hiện vấn đề toàn vẹn",
        "verify_bad_msg": "{n} vấn đề trong {name}.",
        "lan_err": "Lệnh LAN thất bại (mã {rc}). {err}",
        "lan_on_word": "BẬT",
        "lan_off_word": "TẮT",
        "lan_enable_msg": "Đã bật mặc định LAN. Khởi động lại dashboard để áp dụng.",
        "lan_phone_prefix": " Mở từ điện thoại: ",
        "lan_disable_msg": "Đã tắt mặc định LAN — quay về localhost-only.",
        "fw_err": "Mở firewall thất bại (mã {rc}). {err}",
        "fw_title": "Firewall LAN",
        "fw_opened": "Đã mở cổng inbound cho LAN (chỉ local subnet).",
        "fw_failed": ("Không mở được — cần quyền admin. Chạy lệnh dưới trong PowerShell "
                      "(Run as administrator), hoặc bấm đúp win/lan_on.bat (tự nâng quyền UAC)."),
        "fw_manual": "Trên hệ này hãy chạy lệnh dưới thủ công.",
        "fw_dryrun": "(dry-run) lệnh sẽ chạy:",
        "as_err": "Lệnh autostart thất bại (mã {rc}). {err}",
        "as_title": "Tự khởi động",
        "as_enabled": "Đã bật tự khởi động lúc đăng nhập (chạy ẩn).",
        "as_removed": "Đã tắt tự khởi động.",
        "as_failed": ("Không tạo được tác vụ — cần quyền admin. Bấm đúp "
                      "win/autostart_on.bat (tự nâng quyền UAC)."),
        "as_notfound": "Không có tác vụ tự khởi động để xoá.",
        "as_manual": "Trên hệ này hãy cấu hình systemd thủ công (xem chi tiết).",
        "restore_title": "Khôi phục",
        "restore_preview_err": "Xem trước thất bại (mã {rc}). {err}",
        "restore_refused_title": "Bị từ chối — cây chưa commit",
        "restore_refused_msg": ("Cây làm việc có thay đổi chưa commit. Commit/stash trước, hoặc tick "
                                "“allow_dirty” để ghi đè có chủ đích."),
        "restore_apply_err": "Khôi phục thất bại (mã {rc}). {err}",
        "restore_stale_title": "Bị hủy — kế hoạch đã lệch [aborted-stale]",
        "restore_stale_msg": ("Cây đã thay đổi kể từ lúc xem trước nên plan-hash bị lệch; không ghi "
                              "gì cả. Xem trước lại để lấy hash mới."),
        "restore_done_title": "Đã khôi phục",
        "restore_done_msg": ("Đã ghi {written} tệp từ {name}. Tự sao lưu trước khi ghi: {backup}."),
        "restore_backup_none": "không có",
        "restore_expected": "expected {expected}",
        "restore_actual": "actual {actual}",
    },
    "en": {
        "err_title": "Error",
        "login_locked": "Locked out after too many failed attempts. Try again later.",
        "login_wrong": "Wrong password.",
        "pw_denied_title": "Denied",
        "pw_wrong_old": "The old password is incorrect.",
        "pw_too_short": "The new password must be at least {min} characters.",
        "pw_changed_title": "Password changed",
        "pw_changed_msg": "The admin password has changed. New logins use this password.",
        "restart_err": "Couldn't restart: {exc}",
        "restart_title": "Restarting",
        "restart_msg": ("Spawned a detached restart process (PID {pid}). "
                        "The page will reconnect once the dashboard is back."),
        "snap_err": "Snapshot failed (code {rc}). {err}",
        "snap_title": "Working tree snapshotted",
        "snap_msg": "Snapshot saved: {name}",
        "pack_err": "Pack failed (code {rc}). {err}",
        "pack_title": "Release packed",
        "pack_msg": "Release: {name} ({files} payload files).",
        "verify_err": "Verify failed (code {rc}). {err}",
        "verify_ok_title": "Integrity check",
        "verify_ok_msg": "Release {name} is intact — every sha256 matches the manifest.",
        "verify_bad_title": "Integrity problems found",
        "verify_bad_msg": "{n} problems in {name}.",
        "lan_err": "LAN command failed (code {rc}). {err}",
        "lan_on_word": "ON",
        "lan_off_word": "OFF",
        "lan_enable_msg": "LAN default enabled. Restart the dashboard to apply.",
        "lan_phone_prefix": " Open from a phone: ",
        "lan_disable_msg": "LAN default disabled — back to localhost-only.",
        "fw_err": "Opening the firewall failed (code {rc}). {err}",
        "fw_title": "LAN firewall",
        "fw_opened": "Opened the inbound port for LAN (local subnet only).",
        "fw_failed": ("Couldn't open it — needs admin. Run the command below in PowerShell "
                      "(Run as administrator), or double-click win/lan_on.bat (self-elevates via UAC)."),
        "fw_manual": "On this system, run the command below manually.",
        "fw_dryrun": "(dry-run) the command would run:",
        "as_err": "Autostart command failed (code {rc}). {err}",
        "as_title": "Autostart",
        "as_enabled": "Autostart at login enabled (runs hidden).",
        "as_removed": "Autostart disabled.",
        "as_failed": ("Couldn't create the task — needs admin. Double-click "
                      "win/autostart_on.bat (self-elevates via UAC)."),
        "as_notfound": "No autostart task to remove.",
        "as_manual": "On this system, configure systemd manually (see details).",
        "restore_title": "Restore",
        "restore_preview_err": "Preview failed (code {rc}). {err}",
        "restore_refused_title": "Denied — uncommitted tree",
        "restore_refused_msg": ("The working tree has uncommitted changes. Commit/stash first, or tick "
                                "“allow_dirty” to overwrite on purpose."),
        "restore_apply_err": "Restore failed (code {rc}). {err}",
        "restore_stale_title": "Aborted — plan drifted [aborted-stale]",
        "restore_stale_msg": ("The tree changed since the preview, so the plan-hash no longer matches; "
                              "nothing was written. Preview again to get a fresh hash."),
        "restore_done_title": "Restored",
        "restore_done_msg": ("Wrote {written} files from {name}. Auto-backup before writing: {backup}."),
        "restore_backup_none": "none",
        "restore_expected": "expected {expected}",
        "restore_actual": "actual {actual}",
    },
}


def catalog(lang: str) -> dict:
    """Template strings for one language (validated)."""
    return _UI[normalize_lang(lang)]


def admin_msg(lang: str) -> dict:
    """Server-rendered /admin result messages for one language (validated)."""
    return _ADMIN[normalize_lang(lang)]


def js_strings(lang: str) -> dict:
    """Strings used inside dashboard.js, shipped to the page as an embedded JSON blob."""
    return _JS[normalize_lang(lang)]


def tier_labels(lang: str) -> dict:
    """tier id -> human label, for one language (validated)."""
    return TIER_LABELS[normalize_lang(lang)]
