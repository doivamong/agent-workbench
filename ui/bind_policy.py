"""ui/bind_policy.py — classify a dashboard bind host; refuse Internet-facing exposure.

Stdlib-only (``ipaddress``). Shared by ``ui/web/app.py`` (enforcement in ``create_app``),
``ui/web/admin.py`` (the LAN-reachability badge), and ``ops/dashboard_ctl.py`` (a pre-flight
refusal before it spawns the server) — so the policy lives in **one** place. A security
classifier must not drift between copied implementations.

Policy: the dashboard speaks **plain HTTP** and, once an admin password is set, that password
and the session cookie travel in **cleartext**. So it must never bind directly to a public /
Internet-routable address. Allowed:

  * **loopback** (127.0.0.0/8, ::1) — this machine only;
  * **private LAN** (RFC 1918 / fc00::/7 / link-local) — reachable on the home network;
  * **unspecified** (0.0.0.0, ::) — "all interfaces", the sanctioned LAN-read-only mode whose
    actual reach is scoped by the host firewall (see ops/lan_setup.py → RemoteAddress LocalSubnet).

Refused: a literal, globally-routable **public** IP. To reach the dashboard from a domain, keep
it on localhost/LAN and put a reverse proxy or a **Cloudflare Tunnel** in front — it terminates
TLS and connects to the app locally, so the app never needs a public bind.
"""
from __future__ import annotations

import ipaddress


def bind_scope(host: str) -> str:
    """Classify a bind host into ``'localhost'`` | ``'lan'`` | ``'public'`` | ``'hostname'``.

    ``'lan'`` covers the unspecified address (0.0.0.0 / ::, all interfaces) and the private /
    link-local ranges — reachable on the local network. A non-literal (a DNS name) is
    ``'hostname'``: it can't be classified by IP here, so it is treated as non-public (the safe
    Internet path binds to localhost, never to a public name)."""
    try:
        ip = ipaddress.ip_address(host.strip().strip("[]"))
    except ValueError:
        return "hostname"
    if ip.is_loopback:
        return "localhost"
    if ip.is_unspecified or ip.is_private or ip.is_link_local:
        return "lan"
    return "public"


def is_public_bind_host(host: str) -> bool:
    """True only when ``host`` is a literal, globally-routable IP (a public / WAN address)."""
    return bind_scope(host) == "public"


def public_bind_refusal(host: str) -> str:
    """The plain-language reason for refusing a public bind — it names the risk and points at
    the safe path (a reverse proxy / Cloudflare Tunnel), so the message guides instead of just
    saying 'no'."""
    return (
        f"refusing to bind the dashboard to the public address {host!r}: it serves plain HTTP "
        "and, with an admin password set, that password travels in cleartext — exposing it "
        "directly to the Internet is unsafe. For your home LAN, bind 0.0.0.0 with the firewall "
        "scoped to the local subnet. To reach it from a domain, keep the app on localhost/LAN "
        "and put a reverse proxy or a Cloudflare Tunnel (which terminates TLS and connects to "
        "the app locally) in front — never a direct public bind."
    )
