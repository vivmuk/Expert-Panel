"""Partner-key usage dashboard. Not a public page.

The HTML is rendered on Railway from the user database. A proxy host forwards
the request and never reads Postgres itself.
"""
from html import escape

from flask import Blueprint, Response, redirect, request

from ..backend_proxy import forward_admin
from ..hostrole import account_role
from ..keys import verify_key
from ..spendguard import CLOSED
from .access import listed_key
from .pages import FOOT, head, header

bp = Blueprint("analytics", __name__)

ADMIN_COOKIE = "ai_partner_admin"


def _raw_key():
    header = request.headers.get("Authorization", "")
    token = header[7:].strip() if header.startswith("Bearer ") else ""
    if token.startswith("sess_"):
        token = ""
    if token:
        return token
    return request.cookies.get(ADMIN_COOKIE, "").strip()


def _presented_key():
    candidate = _raw_key()
    if candidate and (listed_key(candidate) or verify_key(candidate)):
        return candidate
    return ""


def _wants_json():
    accept = request.headers.get("Accept", "")
    return "application/json" in accept and "text/html" not in accept


def _money(value):
    if value is None:
        return "unknown"
    return str(int(value))


def _when(value):
    if value is None:
        return ""
    text = value.isoformat() if hasattr(value, "isoformat") else str(value)
    return escape(text)


@bp.get("/admin/usage")
def usage_page():
    if account_role() != "authority":
        raw = _raw_key()
        if not raw:
            if _wants_json():
                return _json_denied()
            return _html(_gate("Enter the partner key to view usage."), 401)
        return forward_admin(raw)
    if not _presented_key():
        if _wants_json():
            return _json_denied()
        return _html(_gate("Enter the partner key to view usage."), 401)
    from ..accounts import AccountsUnavailable, usage_report

    try:
        report = usage_report()
    except AccountsUnavailable:
        return _html(_gate(CLOSED["accounts_unavailable"]), 503)
    return _html(_render(report), 200)


@bp.post("/admin/usage/session")
def usage_session():
    key = (request.form.get("key") or "").strip()
    if account_role() != "authority":
        if not key:
            return _html(_gate("Enter the partner key to view usage."), 401)
        response = redirect("/admin/usage")
        response.set_cookie(
            ADMIN_COOKIE,
            key,
            max_age=12 * 3600,
            httponly=True,
            samesite="Lax",
            secure=request.is_secure,
            path="/admin",
        )
        return response
    if not key or not (listed_key(key) or verify_key(key)):
        return _html(_gate("That key was not accepted."), 401)
    response = redirect("/admin/usage")
    response.set_cookie(
        ADMIN_COOKIE,
        key,
        max_age=12 * 3600,
        httponly=True,
        samesite="Lax",
        secure=request.is_secure,
        path="/admin",
    )
    return response


def _json_denied():
    from flask import jsonify

    return jsonify({"error": {"code": "unauthorized", "message": "A partner key is required."}}), 401


def _html(body, status):
    return Response(
        body,
        status=status,
        content_type="text/html; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


def _gate(message):
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
{head("AI Partner · Usage")}
</head>
<body>
{header("")}
<main class="wrap" id="main">
  <section class="page-head">
    <p class="kicker">Partners</p>
    <h1>Usage</h1>
    <p class="lede">Signups, questions, and measured cost. This page does not list accounts until the partner key is accepted.</p>
  </section>
  <form class="form-card gb" method="post" action="/admin/usage/session">
    <div class="field">
      <label for="key">Partner key</label>
      <input id="key" name="key" type="password" autocomplete="off" required>
    </div>
    <button class="btn primary" type="submit">Open usage</button>
    <p class="status-line" role="status">{escape(message)}</p>
  </form>
</main>
{FOOT}
</body>
</html>
"""
    return page


def _rows(items, cells):
    if not items:
        return "<tr><td colspan=\"8\">None yet.</td></tr>"
    return "".join("<tr>" + "".join(f"<td>{cell(item)}</td>" for cell in cells) + "</tr>" for item in items)


def _source_rows(sources):
    order = ("email", "keiki", "agent", "web")
    return "".join(
        "<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            escape(name),
            int((sources.get(name) or {}).get("connections") or 0),
            int((sources.get(name) or {}).get("events") or 0),
        )
        for name in order
    )


def _connection_rows(rows):
    if not rows:
        return "<tr><td colspan=\"8\">None yet.</td></tr>"
    return "".join(
        "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            escape(item.get("source") or ""),
            escape(item.get("identity") or ""),
            _when(item.get("created_at")),
            int(item.get("events") or 0),
        )
        for item in rows
    )


def _render(report):
    users = _rows(
        report["users"],
        (
            lambda item: escape(item["email"]),
            lambda item: _when(item["created_at"]),
            lambda item: str(item["questions_used"]),
            lambda item: str(item["questions_remaining"]),
            lambda item: str(item["questions_granted"]),
        ),
    )
    questions = _rows(
        report["questions"],
        (
            lambda item: _when(item["created_at"]),
            lambda item: escape(item["email"]),
            lambda item: escape(item["route"] or ""),
            lambda item: escape(item["chat_id"] or ""),
        ),
    )
    runs = _rows(
        report["runs"],
        (
            lambda item: _when(item["created_at"]),
            lambda item: escape(item["email"] or ""),
            lambda item: escape(item["route"] or ""),
            lambda item: escape(item["status"] or ""),
            lambda item: escape(item["provider"] or ""),
            lambda item: _money(item["reserved_microusd"]),
            lambda item: _money(item["calculated_microusd"]),
            lambda item: _money(item["billed_microusd"]),
        ),
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{head("AI Partner · Usage")}
</head>
<body>
{header("")}
<main class="wrap" id="main">
  <section class="page-head">
    <p class="kicker">Partners</p>
    <h1>Usage</h1>
    <p class="lede">A question is one signed-in prompt that starts paid provider work. Intake does not count. Unknown cost stays unknown.</p>
  </section>
  <section class="usage-summary" aria-label="Signups">
    <p class="kicker">Email signups</p>
    <p class="usage-count">{int(report["signups"])}</p>
  </section>
  <section aria-labelledby="sources-title">
    <h2 id="sources-title">Connections</h2>
    <table class="usage-table">
      <thead><tr><th>Source</th><th>People</th><th>Events</th></tr></thead>
      <tbody>{_source_rows(report.get("sources") or {})}</tbody>
    </table>
    <table class="usage-table">
      <thead><tr><th>Source</th><th>Identity</th><th>Since</th><th>Events</th></tr></thead>
      <tbody>{_connection_rows(report.get("connections") or [])}</tbody>
    </table>
  </section>
  <section aria-labelledby="users-title">
    <h2 id="users-title">Users</h2>
    <table class="usage-table">
      <thead><tr><th>Email</th><th>Signed up</th><th>Used</th><th>Remaining</th><th>Granted</th></tr></thead>
      <tbody>{users}</tbody>
    </table>
  </section>
  <section aria-labelledby="questions-title">
    <h2 id="questions-title">Questions</h2>
    <table class="usage-table">
      <thead><tr><th>When</th><th>Email</th><th>Route</th><th>Chat</th></tr></thead>
      <tbody>{questions}</tbody>
    </table>
  </section>
  <section aria-labelledby="runs-title">
    <h2 id="runs-title">Runs</h2>
    <table class="usage-table">
      <thead><tr><th>When</th><th>Email</th><th>Route</th><th>Status</th><th>Provider</th><th>Reserved</th><th>Calculated</th><th>Billed</th></tr></thead>
      <tbody>{runs}</tbody>
    </table>
  </section>
</main>
{FOOT}
</body>
</html>
"""
