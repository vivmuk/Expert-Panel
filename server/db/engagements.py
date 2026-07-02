"""Engagement + revision persistence. Every saved analysis or work chart is an
engagement; each generation or update appends an immutable revision."""
import json

from . import connect


def create_engagement(mode, title, status="running"):
    conn = connect()
    try:
        cur = conn.execute(
            "INSERT INTO engagements (mode, title, status) VALUES (?, ?, ?)",
            (mode, title, status),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def add_revision(engagement_id, input_data, result=None, usage=None, note=None, cost_usd=0.0):
    conn = connect()
    try:
        row = conn.execute(
            "SELECT COALESCE(MAX(rev), 0) + 1 AS next_rev FROM revisions WHERE engagement_id = ?",
            (engagement_id,),
        ).fetchone()
        rev = row["next_rev"]
        conn.execute(
            """INSERT INTO revisions
               (engagement_id, rev, note, input_json, result_json, usage_json, cost_usd)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                engagement_id,
                rev,
                note,
                json.dumps(input_data),
                json.dumps(result) if result is not None else None,
                json.dumps(usage) if usage is not None else None,
                cost_usd,
            ),
        )
        conn.execute(
            """UPDATE engagements SET
                 updated_at = datetime('now'),
                 total_cost_usd = total_cost_usd + ?,
                 total_tokens = total_tokens + ?
               WHERE id = ?""",
            (
                cost_usd,
                int((usage or {}).get("total_prompt_tokens", 0))
                + int((usage or {}).get("total_completion_tokens", 0)),
                engagement_id,
            ),
        )
        conn.commit()
        return rev
    finally:
        conn.close()


def set_status(engagement_id, status, title=None):
    conn = connect()
    try:
        if title:
            conn.execute(
                "UPDATE engagements SET status = ?, title = ?, updated_at = datetime('now') WHERE id = ?",
                (status, title, engagement_id),
            )
        else:
            conn.execute(
                "UPDATE engagements SET status = ?, updated_at = datetime('now') WHERE id = ?",
                (status, engagement_id),
            )
        conn.commit()
    finally:
        conn.close()


def list_engagements(mode=None, query=None, limit=50, offset=0):
    conn = connect()
    try:
        sql = """SELECT e.*, (SELECT COUNT(*) FROM revisions r WHERE r.engagement_id = e.id) AS revision_count
                 FROM engagements e WHERE 1=1"""
        params = []
        if mode:
            sql += " AND e.mode = ?"
            params.append(mode)
        if query:
            sql += " AND e.title LIKE ?"
            params.append(f"%{query}%")
        sql += " ORDER BY e.updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_engagement(engagement_id):
    conn = connect()
    try:
        row = conn.execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,)).fetchone()
        if not row:
            return None
        engagement = dict(row)
        revisions = conn.execute(
            "SELECT rev, note, cost_usd, created_at FROM revisions WHERE engagement_id = ? ORDER BY rev",
            (engagement_id,),
        ).fetchall()
        engagement["revisions"] = [dict(r) for r in revisions]
        latest = conn.execute(
            "SELECT * FROM revisions WHERE engagement_id = ? ORDER BY rev DESC LIMIT 1",
            (engagement_id,),
        ).fetchone()
        if latest:
            engagement["latest"] = _revision_to_dict(latest)
        return engagement
    finally:
        conn.close()


def get_revision(engagement_id, rev):
    conn = connect()
    try:
        row = conn.execute(
            "SELECT * FROM revisions WHERE engagement_id = ? AND rev = ?",
            (engagement_id, rev),
        ).fetchone()
        return _revision_to_dict(row) if row else None
    finally:
        conn.close()


def _revision_to_dict(row):
    d = dict(row)
    for key in ("input_json", "result_json", "usage_json"):
        raw = d.pop(key, None)
        d[key.replace("_json", "")] = json.loads(raw) if raw else None
    return d


def rename_engagement(engagement_id, title):
    conn = connect()
    try:
        conn.execute(
            "UPDATE engagements SET title = ?, updated_at = datetime('now') WHERE id = ?",
            (title, engagement_id),
        )
        conn.commit()
    finally:
        conn.close()


def delete_engagement(engagement_id):
    conn = connect()
    try:
        conn.execute("DELETE FROM engagements WHERE id = ?", (engagement_id,))
        conn.commit()
    finally:
        conn.close()


def save_run_events(run_id, events):
    conn = connect()
    try:
        conn.executemany(
            "INSERT OR IGNORE INTO run_events (run_id, seq, event_type, data_json) VALUES (?, ?, ?, ?)",
            [(run_id, e["seq"], e["type"], json.dumps(e["data"])) for e in events],
        )
        conn.commit()
    finally:
        conn.close()
