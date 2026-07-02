"""In-process run registry.

Each run owns an append-only event log plus per-subscriber queues. The full log
enables Last-Event-ID replay for reconnecting SSE clients and is flushed to
SQLite when the run finishes. This registry is in-memory, which pins the app to
a single gunicorn worker (documented in README); the run_events table is the
escape hatch if multi-worker is ever needed.
"""
import json
import queue
import threading
import time
import uuid


class Run:
    def __init__(self, run_id, mode, engagement_id=None):
        self.id = run_id
        self.mode = mode
        self.engagement_id = engagement_id
        self.status = "running"  # running | waiting_input | completed | failed | cancelled
        self.created_at = time.time()
        self.events = []
        self.result = None
        self.error = None
        self._subscribers = []
        self._lock = threading.Lock()
        self._answers = None
        self._answer_event = threading.Event()
        self.cancel_requested = threading.Event()

    # ------------------------------------------------------------- events
    def emit(self, event_type, data):
        with self._lock:
            seq = len(self.events) + 1
            event = {"seq": seq, "type": event_type, "data": data}
            self.events.append(event)
            subscribers = list(self._subscribers)
        for q in subscribers:
            q.put(event)
        return event

    def subscribe(self, after_seq=0):
        q = queue.Queue()
        with self._lock:
            backlog = [e for e in self.events if e["seq"] > after_seq]
            self._subscribers.append(q)
        for e in backlog:
            q.put(e)
        return q

    def unsubscribe(self, q):
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    # ------------------------------------------------- interactive answers
    def wait_for_answers(self, timeout):
        self.status = "waiting_input"
        got = self._answer_event.wait(timeout)
        self.status = "running"
        if not got:
            raise TimeoutError("Timed out waiting for user answers")
        answers = self._answers
        self._answers = None
        self._answer_event.clear()
        return answers

    def provide_answers(self, answers):
        self._answers = answers
        self._answer_event.set()


class RunRegistry:
    def __init__(self):
        self._runs = {}
        self._lock = threading.Lock()

    def create(self, mode, engagement_id=None):
        run_id = f"r_{uuid.uuid4().hex[:12]}"
        run = Run(run_id, mode, engagement_id)
        with self._lock:
            self._runs[run_id] = run
            self._prune_locked()
        return run

    def get(self, run_id):
        with self._lock:
            return self._runs.get(run_id)

    def _prune_locked(self, max_age_seconds=86400, keep=200):
        if len(self._runs) <= keep:
            return
        cutoff = time.time() - max_age_seconds
        for rid in [r for r, run in self._runs.items() if run.created_at < cutoff]:
            del self._runs[rid]


REGISTRY = RunRegistry()


def sse_format(event):
    return f"id: {event['seq']}\nevent: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"
