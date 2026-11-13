"""User, session, question, and cost rows. Railway Postgres only.

A question is one signed-in prompt that starts paid provider work: a product
chat turn that leaves intake, a stateless /chat message, or an artifact
request. Intake does not insert a question. Unknown costs stay NULL.
"""
import hashlib
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

from psycopg import sql
from psycopg.rows import dict_row

from .hostrole import database_allowed

FREE_QUESTIONS = 3
MAGIC_TTL = timedelta(minutes=20)
SESSION_TTL = timedelta(days=14)
SCHEMA_NAME = re.compile(r"acct_[a-z0-9]{16}")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS app_user (
    id text PRIMARY KEY,
    email text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    questions_granted integer NOT NULL DEFAULT 3
);
CREATE TABLE IF NOT EXISTS magic_link (
    id text PRIMARY KEY,
    user_id text NOT NULL REFERENCES app_user (id),
    token_hash text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    used_at timestamptz
);
CREATE TABLE IF NOT EXISTS session (
    id text PRIMARY KEY,
    user_id text NOT NULL REFERENCES app_user (id),
    token_hash text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz
);
CREATE TABLE IF NOT EXISTS question (
    id text PRIMARY KEY,
    user_id text NOT NULL REFERENCES app_user (id),
    created_at timestamptz NOT NULL DEFAULT now(),
    route text NOT NULL,
    chat_id text
);
CREATE TABLE IF NOT EXISTS provider_run (
    id text PRIMARY KEY,
    user_id text REFERENCES app_user (id),
    question_id text REFERENCES question (id),
    created_at timestamptz NOT NULL DEFAULT now(),
    route text NOT NULL,
    status text NOT NULL,
    reserved_microusd bigint,
    calculated_microusd bigint,
    billed_microusd bigint,
    provider text
);
CREATE TABLE IF NOT EXISTS connection (
    id text PRIMARY KEY,
    source text NOT NULL,
    identity text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source, identity)
);
CREATE TABLE IF NOT EXISTS usage_event (
    id text PRIMARY KEY,
    connection_id text NOT NULL REFERENCES connection (id),
    source text NOT NULL,
    kind text NOT NULL,
    ref text,
    created_at timestamptz NOT NULL DEFAULT now(),
    reserved_microusd bigint,
    calculated_microusd bigint,
    billed_microusd bigint
);
CREATE TABLE IF NOT EXISTS stored_json (
    kind text NOT NULL,
    item_key text NOT NULL,
    body jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (kind, item_key)
);
"""


class AccountsUnavailable(RuntimeError):
    pass


def _now():
    return datetime.now(timezone.utc)


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _schema_name():
    name = os.environ.get("AI_PARTNER_ACCOUNTS_SCHEMA", "").strip()
    if not name:
        return ""
    if not SCHEMA_NAME.fullmatch(name):
        raise AccountsUnavailable("refusing schema name")
    return name


def connect():
    """Open the user database. Proxy processes raise before any socket."""
    if not database_allowed():
        raise AccountsUnavailable("This process does not open the user database.")
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise AccountsUnavailable("DATABASE_URL is not set.")
    if os.environ.get("AI_PARTNER_ACCOUNTS_TEST") == "1":
        from .pg_authority import connect_throwaway

        connection = connect_throwaway(url, row_factory=dict_row)
    else:
        import psycopg

        connection = psycopg.connect(url, row_factory=dict_row)
    name = _schema_name()
    if name:
        connection.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(name)))
    return connection


def ensure_schema():
    if not database_allowed():
        return
    with connect() as connection:
        connection.execute(SCHEMA_SQL)
        connection.commit()


def install_test_schema(dsn, schema):
    from .pg_authority import connect_throwaway, throwaway_params

    throwaway_params(dsn)
    if not SCHEMA_NAME.fullmatch(schema):
        raise RuntimeError("refusing schema name")
    with connect_throwaway(dsn, autocommit=True) as connection:
        connection.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        connection.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        connection.execute(SCHEMA_SQL)


def drop_test_schema(dsn, schema):
    from .pg_authority import connect_throwaway, throwaway_params

    throwaway_params(dsn)
    if not SCHEMA_NAME.fullmatch(schema):
        raise RuntimeError("refusing schema name")
    with connect_throwaway(dsn, autocommit=True) as connection:
        connection.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))


def _user_row(connection, user_id):
    row = connection.execute(
        """SELECT id, email, created_at, questions_granted,
                  (SELECT count(*) FROM question WHERE user_id = app_user.id) AS questions_used
           FROM app_user WHERE id = %s""",
        (user_id,),
    ).fetchone()
    if row is None:
        return None
    used = int(row["questions_used"])
    granted = int(row["questions_granted"])
    return {
        "id": row["id"],
        "email": row["email"],
        "created_at": row["created_at"],
        "questions_granted": granted,
        "questions_used": used,
        "questions_remaining": max(0, granted - used),
    }


def ensure_user(email):
    with connect() as connection:
        row = connection.execute("SELECT id FROM app_user WHERE email = %s", (email,)).fetchone()
        if row is None:
            user_id = secrets.token_hex(16)
            connection.execute(
                "INSERT INTO app_user (id, email, questions_granted) VALUES (%s, %s, %s)",
                (user_id, email, FREE_QUESTIONS),
            )
        else:
            user_id = row["id"]
        connection.commit()
        return _user_row(connection, user_id)


def issue_magic_link(email):
    user = ensure_user(email)
    token = "ml_" + secrets.token_urlsafe(32)
    with connect() as connection:
        connection.execute(
            """INSERT INTO magic_link (id, user_id, token_hash, expires_at)
               VALUES (%s, %s, %s, %s)""",
            (secrets.token_hex(16), user["id"], _hash(token), _now() + MAGIC_TTL),
        )
        connection.commit()
    return token


def consume_magic_link(token):
    if not isinstance(token, str) or not token.startswith("ml_"):
        return None
    with connect() as connection:
        row = connection.execute(
            """UPDATE magic_link SET used_at = now()
               WHERE token_hash = %s AND used_at IS NULL AND expires_at > now()
               RETURNING user_id""",
            (_hash(token),),
        ).fetchone()
        if row is None:
            connection.rollback()
            return None
        session_token = "sess_" + secrets.token_urlsafe(32)
        connection.execute(
            """INSERT INTO session (id, user_id, token_hash, expires_at)
               VALUES (%s, %s, %s, %s)""",
            (secrets.token_hex(16), row["user_id"], _hash(session_token), _now() + SESSION_TTL),
        )
        connection.commit()
        return session_token


def user_for_session(token):
    if not isinstance(token, str) or not token.startswith("sess_"):
        return None
    with connect() as connection:
        row = connection.execute(
            """SELECT user_id FROM session
               WHERE token_hash = %s AND revoked_at IS NULL AND expires_at > now()""",
            (_hash(token),),
        ).fetchone()
        if row is None:
            return None
        return _user_row(connection, row["user_id"])


def revoke_session(token):
    if not isinstance(token, str) or not token:
        return
    with connect() as connection:
        connection.execute(
            "UPDATE session SET revoked_at = now() WHERE token_hash = %s AND revoked_at IS NULL",
            (_hash(token),),
        )
        connection.commit()


def latest_question(user_id, chat_id):
    """The question already charged for this chat, if the user has one."""
    if not user_id or not chat_id:
        return None
    with connect() as connection:
        row = connection.execute(
            """SELECT question.id AS question_id, provider_run.id AS run_id, question.user_id
               FROM question
               JOIN provider_run ON provider_run.question_id = question.id
               WHERE question.user_id = %s AND question.chat_id = %s
               ORDER BY question.created_at DESC
               LIMIT 1""",
            (user_id, chat_id),
        ).fetchone()
        return dict(row) if row else None


def consume_question(user_id, route, chat_id=None):
    """Insert one question and a cost row whose amounts start as NULL.

    Returns the question row, or None when the account has none left.
    """
    with connect() as connection:
        locked = connection.execute(
            "SELECT id, questions_granted FROM app_user WHERE id = %s FOR UPDATE",
            (user_id,),
        ).fetchone()
        if locked is None:
            connection.rollback()
            return None
        used = connection.execute(
            "SELECT count(*) AS n FROM question WHERE user_id = %s",
            (user_id,),
        ).fetchone()["n"]
        if int(used) >= int(locked["questions_granted"]):
            connection.rollback()
            return None
        question_id = secrets.token_hex(16)
        run_id = secrets.token_hex(16)
        connection.execute(
            "INSERT INTO question (id, user_id, route, chat_id) VALUES (%s, %s, %s, %s)",
            (question_id, user_id, route, chat_id),
        )
        connection.execute(
            """INSERT INTO provider_run (
                   id, user_id, question_id, route, status,
                   reserved_microusd, calculated_microusd, billed_microusd, provider
               ) VALUES (%s, %s, %s, %s, 'started', NULL, NULL, NULL, NULL)""",
            (run_id, user_id, question_id, route),
        )
        connection.commit()
        return {"question_id": question_id, "run_id": run_id, "user_id": user_id}


def set_run_costs(run_id, *, reserved=None, calculated=None, billed=None, provider=None, status=None):
    """Write only fields that are actually known. NULL stays NULL."""
    assignments = []
    values = []
    for name, value in (
        ("reserved_microusd", reserved),
        ("calculated_microusd", calculated),
        ("billed_microusd", billed),
    ):
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("cost must be a non-negative integer or null")
        assignments.append(f"{name} = %s")
        values.append(value)
    if provider is not None:
        assignments.append("provider = %s")
        values.append(provider)
    if status is not None:
        assignments.append("status = %s")
        values.append(status)
    if not assignments:
        return
    values.append(run_id)
    with connect() as connection:
        connection.execute(
            f"UPDATE provider_run SET {', '.join(assignments)} WHERE id = %s",
            values,
        )
        connection.commit()


def runs_for_user(user_id):
    with connect() as connection:
        rows = connection.execute(
            """SELECT id, question_id, created_at, route, status,
                      reserved_microusd, calculated_microusd, billed_microusd, provider
               FROM provider_run WHERE user_id = %s ORDER BY created_at""",
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def usage_report():
    with connect() as connection:
        users = connection.execute(
            """SELECT id, email, created_at, questions_granted,
                      (SELECT count(*) FROM question q WHERE q.user_id = app_user.id) AS questions_used
               FROM app_user ORDER BY created_at"""
        ).fetchall()
        questions = connection.execute(
            """SELECT question.id, question.created_at, question.route, question.chat_id, app_user.email
               FROM question JOIN app_user ON app_user.id = question.user_id
               ORDER BY question.created_at"""
        ).fetchall()
        runs = connection.execute(
            """SELECT provider_run.id, provider_run.created_at, provider_run.route, provider_run.status,
                      provider_run.reserved_microusd, provider_run.calculated_microusd,
                      provider_run.billed_microusd, provider_run.provider, app_user.email
               FROM provider_run LEFT JOIN app_user ON app_user.id = provider_run.user_id
               ORDER BY provider_run.created_at"""
        ).fetchall()
    people = []
    for row in users:
        used = int(row["questions_used"])
        granted = int(row["questions_granted"])
        people.append({
            "id": row["id"],
            "email": row["email"],
            "created_at": row["created_at"],
            "questions_granted": granted,
            "questions_used": used,
            "questions_remaining": max(0, granted - used),
        })
    return {
        "signups": len(people),
        "users": people,
        "questions": [dict(row) for row in questions],
        "runs": [dict(row) for row in runs],
        **connection_report(),
    }


def _cost(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("cost must be a non-negative integer or null")
    return value


def remember_connection(source, identity, kind, ref=None, reserved=None, calculated=None, billed=None):
    """Upsert one principal and append one event. Unknown costs stay null."""
    identity = " ".join(str(identity or "").split())[:200]
    if source not in {"email", "keiki", "agent", "web"} or not identity:
        return
    with connect() as connection:
        row = connection.execute(
            "SELECT id FROM connection WHERE source = %s AND identity = %s",
            (source, identity),
        ).fetchone()
        if row is None:
            connection_id = secrets.token_hex(16)
            connection.execute(
                "INSERT INTO connection (id, source, identity) VALUES (%s, %s, %s)",
                (connection_id, source, identity),
            )
        else:
            connection_id = row["id"]
        connection.execute(
            """INSERT INTO usage_event (
                   id, connection_id, source, kind, ref,
                   reserved_microusd, calculated_microusd, billed_microusd
               ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                secrets.token_hex(16),
                connection_id,
                source,
                kind[:40],
                (ref or None),
                _cost(reserved),
                _cost(calculated),
                _cost(billed),
            ),
        )
        connection.commit()


def connection_report():
    with connect() as connection:
        rows = connection.execute(
            """SELECT source, identity, created_at,
                      (SELECT count(*) FROM usage_event e WHERE e.connection_id = connection.id) AS events
               FROM connection ORDER BY created_at"""
        ).fetchall()
    people = [dict(row) for row in rows]
    sources = {}
    for source in ("email", "keiki", "agent", "web"):
        chosen = [item for item in people if item["source"] == source]
        sources[source] = {"connections": len(chosen), "events": sum(int(item["events"]) for item in chosen)}
    return {"sources": sources, "connections": people}


def save_json(kind, item_key, body):
    from psycopg.types.json import Jsonb

    with connect() as connection:
        connection.execute(
            """INSERT INTO stored_json (kind, item_key, body, updated_at)
               VALUES (%s, %s, %s, now())
               ON CONFLICT (kind, item_key)
               DO UPDATE SET body = EXCLUDED.body, updated_at = now()""",
            (kind, item_key, Jsonb(body)),
        )
        connection.commit()


def claim_json(kind, item_key, body):
    """Insert this body when the key is new. Return the body that won the key."""
    from psycopg.types.json import Jsonb

    with connect() as connection:
        row = connection.execute(
            """WITH ins AS (
                   INSERT INTO stored_json (kind, item_key, body, updated_at)
                   VALUES (%s, %s, %s, now())
                   ON CONFLICT (kind, item_key) DO NOTHING
                   RETURNING body
               )
               SELECT body FROM ins
               UNION ALL
               SELECT body FROM stored_json
               WHERE kind = %s AND item_key = %s
                 AND NOT EXISTS (SELECT 1 FROM ins)""",
            (kind, item_key, Jsonb(body), kind, item_key),
        ).fetchone()
        connection.commit()
    if row is None:
        return None
    found = row["body"]
    return found if isinstance(found, dict) else None


def load_json(kind, item_key):
    with connect() as connection:
        row = connection.execute(
            "SELECT body FROM stored_json WHERE kind = %s AND item_key = %s",
            (kind, item_key),
        ).fetchone()
    if row is None:
        return None
    body = row["body"]
    return body if isinstance(body, dict) else None

