"""Three free questions per email, counted only on the Railway authority.

A question is one user-submitted prompt that would call a paid provider:
the product chat turn that leaves intake, a stateless POST /chat message,
or one artifact generation. The browser then sends empty messages to walk
the remaining phases of that same prompt. Those continuations reuse the
question already charged for the chat. Intake does not count. Maritime and
Vercel do not count locally; they forward the prompt.
"""
from contextvars import ContextVar

from flask import has_request_context, request

from .hostrole import account_role, paid_sender
from .spendguard import SpendClosed

_open = ContextVar("open_question", default=None)

COOKIE = "ai_partner_session"
SESSION_HEADER = "X-AI-Partner-Session"


def session_token():
    if not has_request_context():
        return ""
    cookie = request.cookies.get(COOKIE, "")
    if isinstance(cookie, str) and cookie.startswith("sess_"):
        return cookie
    header = request.headers.get(SESSION_HEADER, "").strip()
    if header.startswith("sess_"):
        return header
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer sess_"):
        return auth[7:].strip()
    return ""


def current_user():
    if account_role() != "authority":
        return None
    token = session_token()
    if not token:
        return None
    from .accounts import user_for_session

    return user_for_session(token)


def question_open():
    return _open.get()


def direct_send_allowed():
    row = _open.get()
    return bool(row and row.get("allow_send"))


def begin_question(route, chat_id=None, continuation=False):
    """Consume one question, or raise SpendClosed. Nested calls reuse the open row.

    `continuation` is an empty follow-up the browser sends while `next` is set.
    It reuses the question already stored for this chat instead of charging another.
    """
    existing = _open.get()
    if existing is not None:
        return None
    if account_role() != "authority" or not paid_sender():
        raise SpendClosed("paid_host_closed" if session_token() else "sign_in_required")
    from .accounts import AccountsUnavailable, consume_question, latest_question

    try:
        user = current_user()
    except AccountsUnavailable as exc:
        raise SpendClosed("accounts_unavailable") from exc
    if user is None:
        raise SpendClosed("sign_in_required")
    try:
        if continuation:
            row = latest_question(user["id"], chat_id)
        else:
            row = consume_question(user["id"], route, chat_id)
    except AccountsUnavailable as exc:
        raise SpendClosed("accounts_unavailable") from exc
    if row is None:
        raise SpendClosed("paid_path_blocked" if continuation else "questions_exhausted")
    row = dict(row)
    row["allow_send"] = True
    return _open.set(row)


def end_question(token):
    if token is not None:
        _open.reset(token)


def refusal_for_closed_call():
    """Code for a paid call that is not inside an open question."""
    if account_role() != "authority":
        return "sign_in_required" if not session_token() else "paid_host_closed"
    if not session_token():
        return "sign_in_required"
    try:
        user = current_user()
    except Exception:
        return "accounts_unavailable"
    if user is None:
        return "sign_in_required"
    if user["questions_remaining"] <= 0:
        return "questions_exhausted"
    if not paid_sender():
        return "paid_host_closed"
    return "paid_path_blocked"


def note_known_cost(*, reserved=None, calculated=None, billed=None, provider=None, status=None):
    row = _open.get()
    if not row:
        return
    from .accounts import set_run_costs

    set_run_costs(
        row["run_id"],
        reserved=reserved,
        calculated=calculated,
        billed=billed,
        provider=provider,
        status=status,
    )
