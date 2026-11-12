"""Who connected, and what they ran.

Email questions are capped at three only when a mailer is configured. Keiki
texters are recorded by their channel address and are not asked to sign in.
Agent keys and anonymous web visitors are recorded the same way. A missing
database never blocks the chat.
"""
from contextlib import contextmanager
from contextvars import ContextVar

_actor = ContextVar("usage_actor", default=None)


@contextmanager
def actor(source, identity):
    token = _actor.set((source, str(identity or "")[:200]))
    try:
        yield
    finally:
        _actor.reset(token)


def active_actor():
    return _actor.get()


def note_chat(state, message):
    """Record a paid chat step. Enforce the email allowance only when mail can be sent."""
    pair = _actor.get()
    source, identity = pair if pair else ("web", "")
    if not identity:
        identity = (state or {}).get("chat_id") or "anonymous"
    text = " ".join(str(message or "").split())
    continuation = not text
    if source == "web":
        from .mailer import get_mailer

        if get_mailer() is not None:
            from .entitlement import begin_question, current_user

            token = begin_question("chat", (state or {}).get("chat_id"), continuation=continuation)
            user = current_user()
            if user:
                source, identity = "email", user["email"]
            _remember(source, identity, "run" if continuation else "question", (state or {}).get("chat_id"))
            return token
    _remember(source, identity, "run" if continuation else "question", (state or {}).get("chat_id"))
    return None


def note_event(source, identity, kind, ref=None):
    _remember(source, identity, kind, ref)


def _remember(source, identity, kind, ref):
    from .accounts import AccountsUnavailable, remember_connection
    from .hostrole import database_allowed

    if not database_allowed():
        return
    try:
        remember_connection(source, identity, kind, ref)
    except (AccountsUnavailable, ValueError):
        return
