"""Run lifecycle: create, stream events (SSE), poll, answer, cancel."""
import logging
import queue

from flask import Blueprint, Response, jsonify, request

from ..pipeline.events import REGISTRY, sse_format
from ..pipeline.runner import start_run

logger = logging.getLogger(__name__)
bp = Blueprint("runs", __name__)

HEARTBEAT_SECONDS = 15


@bp.post("/runs")
def create_run():
    payload = request.get_json(force=True, silent=True) or {}
    try:
        run, engagement_id, estimate = start_run(payload)
    except (ValueError, KeyError) as exc:
        return jsonify({"error": {"code": "bad_request", "message": str(exc)}}), 400
    return (
        jsonify({"runId": run.id, "engagementId": engagement_id, "estimate": estimate}),
        202,
    )


@bp.get("/runs/<run_id>")
def get_run(run_id):
    run = REGISTRY.get(run_id)
    if not run:
        return jsonify({"error": {"code": "not_found", "message": "Run not found"}}), 404
    return jsonify(
        {
            "runId": run.id,
            "mode": run.mode,
            "engagementId": run.engagement_id,
            "status": run.status,
            "events": run.events[-200:],
            "error": run.error,
        }
    )


@bp.get("/runs/<run_id>/events")
def stream_events(run_id):
    run = REGISTRY.get(run_id)
    if not run:
        return jsonify({"error": {"code": "not_found", "message": "Run not found"}}), 404

    last_id = request.headers.get("Last-Event-ID") or request.args.get("lastEventId") or 0
    try:
        last_id = int(last_id)
    except ValueError:
        last_id = 0

    def generate():
        q = run.subscribe(after_seq=last_id)
        try:
            while True:
                try:
                    event = q.get(timeout=HEARTBEAT_SECONDS)
                except queue.Empty:
                    if run.status in ("completed", "failed", "cancelled"):
                        break
                    yield ": ping\n\n"
                    continue
                yield sse_format(event)
                if event["type"] in ("run.completed", "run.error"):
                    break
        finally:
            run.unsubscribe(q)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@bp.post("/runs/<run_id>/answers")
def provide_answers(run_id):
    run = REGISTRY.get(run_id)
    if not run:
        return jsonify({"error": {"code": "not_found", "message": "Run not found"}}), 404
    data = request.get_json(force=True, silent=True) or {}
    run.provide_answers(data.get("answers") or {})
    return jsonify({"ok": True})


@bp.post("/runs/<run_id>/cancel")
def cancel(run_id):
    run = REGISTRY.get(run_id)
    if not run:
        return jsonify({"error": {"code": "not_found", "message": "Run not found"}}), 404
    run.cancel_requested.set()
    run.provide_answers({})  # unblock any clarify wait
    return jsonify({"ok": True})
