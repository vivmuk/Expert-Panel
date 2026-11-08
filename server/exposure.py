"""Offline application-exposure contract. Not a production cap and not an invoice.

A reservation is the sum of synthetic or, later, verified schedule rows for one
frozen request. This module ships no verified prices. Caller-supplied
`unit_microusd` is rejected. Postgres is not connected. `MemoryAuthority` is
one process, under one lock, standing in for a transaction that is not written
yet. HTTP does not install an authority.

5000000 microusd and 3 executions are the limits that lock enforces on that
object. They are not a provider bill. A copied process is a second cap.
"""
import hashlib
import json
import secrets
import threading
from contextvars import ContextVar

from .spendguard import SpendClosed, refuse_paid
from .venice.client import MAX_ATTEMPTS as VENICE_UPSTREAM_TRIES

APPLICATION_CEILING_MICROUSD = 5_000_000
MAX_ENGAGEMENT_ATTEMPTS = 3
POSTGRES_INTEGRATION = "pending"
_SERVICES = frozenset({"venice", "exa", "memory", "voice", "image"})
_ENVELOPE_KEYS = ("service", "model", "input_bytes", "output_tokens", "duration_seconds", "items")

_current = ContextVar("exposure_execution", default=None)


class ExposureStop(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class UncertainOutcome(Exception):
    """The offline transport does not know whether a send landed."""


class OfflineTransport:
    """Canned results only. These methods must not open a socket."""

    def venice(self, request):
        del request
        raise UncertainOutcome()

    def search(self, request):
        del request
        raise UncertainOutcome()

    def recall(self, request):
        del request
        raise UncertainOutcome()

    def remember(self, request):
        del request
        raise UncertainOutcome()

    def voice(self, request):
        del request
        raise UncertainOutcome()

    def image(self, request):
        del request
        raise UncertainOutcome()


def current():
    return _current.get()


def activation_blockers():
    return (
        "no_shared_authority_across_hosts",
        "no_verified_price_schedule",
        "postgres_integration_pending",
        "http_has_no_authority",
        "provider_invoice_unknown",
        "restore_not_detected",
    )


def _positive_int(value):
    return not isinstance(value, bool) and isinstance(value, int) and value > 0


def _payload_hash(payload):
    if isinstance(payload, str):
        payload = payload.encode()
    if not isinstance(payload, (bytes, bytearray)) or not payload:
        raise ExposureStop("request_rejected")
    return hashlib.sha256(bytes(payload)).hexdigest()


def quote(schedule, requests):
    """One frozen quote from schedule rows. The request list is copied here."""
    if not isinstance(schedule, list) or not schedule or not isinstance(requests, list) or not requests:
        raise ExposureStop("price_unknown")
    rows = {}
    for row in schedule:
        if not isinstance(row, dict) or row.get("provenance") != "synthetic":
            raise ExposureStop("price_unknown")
        service = row.get("service")
        model = row.get("model")
        if service not in _SERVICES or not isinstance(model, str) or not model:
            raise ExposureStop("price_unknown")
        if "unit_microusd" not in row or not _positive_int(row.get("unit_microusd")):
            raise ExposureStop("price_unknown")
        for key in ("max_input_bytes", "max_output_tokens", "max_duration_seconds", "max_items", "upstream_tries"):
            if not _positive_int(row.get(key)):
                raise ExposureStop("price_unknown")
        repair = row.get("repair_tries", 0)
        if isinstance(repair, bool) or not isinstance(repair, int) or repair < 0:
            raise ExposureStop("price_unknown")
        rows[(service, model)] = row
    snapshot = []
    total = 0
    for item in requests:
        if not isinstance(item, dict) or "unit_microusd" in item or "calls" in item:
            raise ExposureStop("plan_rejected")
        service = item.get("service")
        model = item.get("model")
        operation = item.get("operation")
        row = rows.get((service, model))
        if row is None or not isinstance(operation, str) or not operation:
            raise ExposureStop("price_unknown")
        payload_sha = _payload_hash(item.get("payload"))
        payload_len = len(item["payload"] if isinstance(item.get("payload"), (bytes, bytearray)) else str(item.get("payload")).encode())
        if item.get("input_bytes") != payload_len:
            raise ExposureStop("envelope_rejected")
        bounds = {}
        for key, limit in (
            ("input_bytes", "max_input_bytes"),
            ("output_tokens", "max_output_tokens"),
            ("duration_seconds", "max_duration_seconds"),
            ("items", "max_items"),
        ):
            value = item.get(key)
            if not _positive_int(value) or value > row[limit]:
                raise ExposureStop("envelope_rejected")
            bounds[key] = value
        tries = row["upstream_tries"] + row["repair_tries"]
        reserved = row["unit_microusd"] * tries
        total += reserved
        snapshot.append({
            "service": service,
            "operation": operation,
            "model": model,
            "bounds": bounds,
            "payload_sha256": payload_sha,
            "upstream_tries": row["upstream_tries"],
            "repair_tries": row["repair_tries"],
            "unit_microusd": row["unit_microusd"],
            "reserved_microusd": reserved,
            "provenance": "synthetic",
        })
    frozen = json.loads(json.dumps(snapshot))
    fingerprint = hashlib.sha256(
        json.dumps(frozen, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return total, frozen, fingerprint


class MemoryAuthority:
    """One lock, one process. Postgres integration is pending. Two instances are two caps."""

    def __init__(self, schedule):
        self._lock = threading.Lock()
        self._schedule = schedule
        self._projects = {}

    def register_project(self):
        project_id = secrets.token_hex(16)
        seal = secrets.token_urlsafe(32)
        with self._lock:
            self._projects[project_id] = {
                "seal": seal,
                "executions": [],
            }
        return {"project_id": project_id, "seal": seal}

    def _project(self, project_id, seal):
        project = self._projects.get(project_id)
        if project is None:
            raise ExposureStop("project_rejected")
        if not isinstance(seal, str) or seal != project["seal"]:
            raise ExposureStop("seal_rejected")
        return project

    def _open(self, project):
        return [item for item in project["executions"] if item["status"] != "void"]

    def begin(self, project_id, seal, requests, execution_id=None):
        reserved, snapshot, fingerprint = quote(self._schedule, requests)
        with self._lock:
            project = self._project(project_id, seal)
            if execution_id is not None:
                if not isinstance(execution_id, str) or not execution_id:
                    raise ExposureStop("execution_rejected")
                named = next((item for item in project["executions"] if item["execution_id"] == execution_id), None)
                if named is None or named["status"] == "void":
                    raise ExposureStop("execution_rejected")
                if named["fingerprint"] != fingerprint:
                    raise ExposureStop("request_mismatch")
            found = next(
                (
                    item for item in project["executions"]
                    if item["fingerprint"] == fingerprint and item["status"] != "void"
                ),
                None,
            )
            if found is not None:
                if found["status"] == "settled":
                    return {
                        "kind": "reuse",
                        "execution_id": found["execution_id"],
                        "result": found["result"],
                        "reserved_microusd": found["reserved_microusd"],
                        "snapshot": found["snapshot"],
                        "fingerprint": fingerprint,
                    }
                raise ExposureStop("attempt_uncertain")
            if any(item["status"] == "uncertain" and not item["reconciled"] for item in project["executions"]):
                raise ExposureStop("project_unreconciled")
            if len(self._open(project)) >= MAX_ENGAGEMENT_ATTEMPTS:
                raise ExposureStop("attempts_exhausted")
            spent = sum(item["reserved_microusd"] for item in self._open(project))
            if spent + reserved > APPLICATION_CEILING_MICROUSD:
                raise ExposureStop("over_cap")
            execution = {
                "execution_id": secrets.token_hex(16),
                "report_id": secrets.token_hex(16),
                "capability": secrets.token_hex(16),
                "fingerprint": fingerprint,
                "status": "reserved",
                "reconciled": False,
                "reserved_microusd": reserved,
                "snapshot": snapshot,
                "used": [],
                "sends": 0,
                "result": None,
            }
            project["executions"].append(execution)
            return {
                "kind": "reserved",
                "execution_id": execution["execution_id"],
                "capability": execution["capability"],
                "reserved_microusd": reserved,
                "snapshot": snapshot,
                "fingerprint": fingerprint,
            }

    def _execution(self, project, execution_id):
        found = next((item for item in project["executions"] if item["execution_id"] == execution_id), None)
        if found is None:
            raise ExposureStop("execution_rejected")
        return found

    def _blocked(self, project):
        return any(item["status"] == "uncertain" and not item["reconciled"] for item in project["executions"])

    def authorize_send(self, project_id, seal, execution_id, capability, actual):
        """Match this helper call to one unused frozen line, then allow the fake send."""
        view = _actual(actual)
        with self._lock:
            project = self._project(project_id, seal)
            if self._blocked(project):
                raise SpendClosed("paid_path_blocked")
            found = self._execution(project, execution_id)
            if found["status"] != "reserved" or found["capability"] != capability:
                raise SpendClosed("paid_path_blocked")
            index = _match_line(found, view)
            if index is None:
                raise SpendClosed("paid_path_blocked")
            found["used"].append(index)
            found["sends"] += 1
            return json.loads(json.dumps(found["snapshot"][index]))

    def mark_uncertain(self, project_id, seal, execution_id):
        with self._lock:
            project = self._project(project_id, seal)
            found = self._execution(project, execution_id)
            if found["status"] == "uncertain":
                return
            if found["status"] != "reserved":
                raise ExposureStop("attempt_uncertain")
            found["status"] = "uncertain"
            found["capability"] = secrets.token_hex(16)
            found["result"] = None

    def void_unsent(self, project_id, seal, execution_id):
        """A reserved row that never authorized a send. This is not a refund."""
        with self._lock:
            project = self._project(project_id, seal)
            found = self._execution(project, execution_id)
            if found["status"] == "void":
                return
            if found["status"] != "reserved" or found["sends"] != 0:
                raise ExposureStop("attempt_uncertain")
            found["status"] = "void"
            found["capability"] = secrets.token_hex(16)

    def settle(self, project_id, seal, execution_id, result):
        if not isinstance(result, str):
            raise ExposureStop("result_unstored")
        with self._lock:
            project = self._project(project_id, seal)
            found = self._execution(project, execution_id)
            if found["status"] != "reserved":
                raise ExposureStop("attempt_uncertain")
            if self._blocked(project):
                found["status"] = "uncertain"
                found["capability"] = secrets.token_hex(16)
                found["result"] = None
                return "uncertain"
            found["status"] = "settled"
            found["capability"] = secrets.token_hex(16)
            found["result"] = result
            return "settled"

    def reconcile(self, project_id, seal, execution_id):
        with self._lock:
            project = self._project(project_id, seal)
            found = self._execution(project, execution_id)
            if found["status"] != "uncertain" or found["reconciled"]:
                raise ExposureStop("attempt_uncertain")
            found["reconciled"] = True

    def accounted(self, project_id, seal):
        with self._lock:
            project = self._project(project_id, seal)
            executions = self._open(project)
            return {
                "engagement_attempts": len(executions),
                "reserved_microusd": sum(item["reserved_microusd"] for item in executions),
                "engagement_attempt_cap_enforced": True,
                "postgres_integration": POSTGRES_INTEGRATION,
                "verified_price": False,
            }

    def report(self, project_id, seal):
        with self._lock:
            project = self._project(project_id, seal)
            executions = []
            for item in self._open(project):
                executions.append({
                    "report_id": item["report_id"],
                    "status": item["status"],
                    "reserved_microusd": item["reserved_microusd"],
                    "price_provenance": "synthetic",
                    "verified_price": False,
                    "services": [
                        {
                            "service": line["service"],
                            "model": line["model"],
                            "upstream_tries": line["upstream_tries"],
                            "repair_tries": line["repair_tries"],
                            "reserved_microusd": line["reserved_microusd"],
                        }
                        for line in item["snapshot"]
                    ],
                    "provider_reported_usage": None,
                    "billed_microusd": None,
                })
            reserved = sum(item["reserved_microusd"] for item in self._open(project))
        return {
            "label": "application_exposure",
            "runtime_enforcement": False,
            "production_cap": False,
            "postgres_integration": POSTGRES_INTEGRATION,
            "price_provenance": "synthetic",
            "verified_price": False,
            "provider_invoice_cap": False,
            "application_ceiling_microusd": APPLICATION_CEILING_MICROUSD,
            "remaining_application_microusd": APPLICATION_CEILING_MICROUSD - reserved,
            "engagement_attempts": len(executions),
            "engagement_attempt_cap": MAX_ENGAGEMENT_ATTEMPTS,
            "engagement_attempt_cap_enforced": True,
            "amounts": {
                "reserved_worst_case_microusd": reserved,
                "provider_reported_usage": None,
                "calculated_microusd": None,
                "billed_microusd": None,
            },
            "gaps": [
                "synthetic_price_not_a_verified_bound",
                "provider_invoice_unknown",
                "postgres_integration_pending",
                "store_is_process_local",
                "restore_not_detected",
            ],
            "executions": executions,
        }


def _actual(actual):
    if not isinstance(actual, dict):
        raise SpendClosed("paid_path_blocked")
    payload = actual.get("payload")
    if isinstance(payload, str):
        payload = payload.encode()
    if not isinstance(payload, (bytes, bytearray)) or not payload:
        raise SpendClosed("paid_path_blocked")
    if actual.get("input_bytes") != len(payload):
        raise SpendClosed("paid_path_blocked")
    return {
        "service": actual.get("service"),
        "operation": actual.get("operation"),
        "model": actual.get("model"),
        "payload_sha256": hashlib.sha256(bytes(payload)).hexdigest(),
        "input_bytes": len(payload),
        "output_tokens": actual.get("output_tokens"),
        "duration_seconds": actual.get("duration_seconds"),
        "items": actual.get("items"),
        "payload": bytes(payload),
    }


def _match_line(execution, view):
    for index, line in enumerate(execution["snapshot"]):
        if index in execution["used"]:
            continue
        bounds = line["bounds"]
        if (
            line["service"] == view["service"]
            and line["operation"] == view["operation"]
            and line["model"] == view["model"]
            and line["payload_sha256"] == view["payload_sha256"]
            and bounds["input_bytes"] == view["input_bytes"]
            and bounds["output_tokens"] == view["output_tokens"]
            and bounds["duration_seconds"] == view["duration_seconds"]
            and bounds["items"] == view["items"]
        ):
            return index
    return None


def _canon(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def describe_venice(model, messages, schema, max_tokens, duration_seconds=1, items=1):
    payload = _canon({"max_tokens": max_tokens, "messages": messages, "model": model, "schema": schema})
    return _described("venice", "chat", model, payload, max_tokens, duration_seconds, items)


def describe_exa(query, limit, duration_seconds=1):
    payload = _canon({"limit": limit, "query": query})
    return _described("exa", "search", "offline", payload, 1, duration_seconds, limit)


def describe_recall(chat_id, query, visitor_id=None, has_history=False):
    payload = _canon({"chat_id": chat_id, "has_history": bool(has_history), "query": query, "visitor_id": visitor_id})
    return _described("memory", "recall", "offline", payload, 1, 1, 1)


def describe_remember(chat_id, content, visitor_id=None):
    payload = _canon({"chat_id": chat_id, "content": content, "visitor_id": visitor_id})
    return _described("memory", "remember", "offline", payload, 1, 1, 1)


def describe_voice(operation, text):
    if isinstance(text, dict):
        blob = text.get("blob")
        mime = text.get("mime")
        if isinstance(blob, str):
            blob = blob.encode()
        if not isinstance(blob, (bytes, bytearray)) or not isinstance(mime, str) or not mime:
            raise ExposureStop("request_rejected")
        mime_bytes = mime.encode()
        payload = b"transcribe\n" + str(len(mime_bytes)).encode() + b"\n" + mime_bytes + b"\n" + bytes(blob)
    elif isinstance(text, (bytes, bytearray)):
        payload = b"bytes\n" + bytes(text)
    else:
        payload = _canon({"operation": operation, "text": text})
    return _described("voice", operation, "offline", payload, 1, 1, 1)


def describe_image(slot, prompt, model):
    payload = _canon({"model": model, "prompt": prompt, "slot": slot})
    return _described("image", "generate", model, payload, 1, 1, 1)


def _described(service, operation, model, payload, output_tokens, duration_seconds, items):
    if isinstance(payload, str):
        payload = payload.encode()
    return {
        "service": service,
        "operation": operation,
        "model": model,
        "payload": payload,
        "input_bytes": len(payload),
        "output_tokens": output_tokens,
        "duration_seconds": duration_seconds,
        "items": items,
    }


class _Active:
    def __init__(self, authority, project_id, seal, execution_id, capability, transport):
        self.authority = authority
        self.project_id = project_id
        self.seal = seal
        self.execution_id = execution_id
        self.capability = capability
        self.transport = transport

    def consume(self, actual):
        frozen = self.authority.authorize_send(
            self.project_id, self.seal, self.execution_id, self.capability, actual
        )
        frozen["payload"] = actual["payload"] if isinstance(actual["payload"], (bytes, bytearray)) else actual["payload"].encode()
        return self.transport, frozen


def _prepare(decision, transport):
    return _Active(
        decision["authority"],
        decision["project_id"],
        decision["seal"],
        decision["execution_id"],
        decision["capability"],
        transport,
    )


def run_execution(authority, project_id, seal, requests, transport, work, execution_id=None):
    """Reserve from the schedule once, then run work. The caller plan is not read again."""
    if not isinstance(authority, MemoryAuthority) or not isinstance(transport, OfflineTransport):
        refuse_paid()
    if _current.get() is not None:
        raise ExposureStop("nested_execution")
    decision = authority.begin(project_id, seal, requests, execution_id=execution_id)
    if decision["kind"] == "reuse":
        return decision
    decision = dict(decision)
    decision["authority"] = authority
    decision["project_id"] = project_id
    decision["seal"] = seal
    try:
        active = _prepare(decision, transport)
    except Exception:
        authority.void_unsent(project_id, seal, decision["execution_id"])
        raise
    token = _current.set(active)
    try:
        try:
            result = work()
        except UncertainOutcome:
            authority.mark_uncertain(project_id, seal, decision["execution_id"])
            raise SpendClosed("phase_uncertain")
        except Exception:
            _stop_after_failure(authority, project_id, seal, decision["execution_id"])
            raise
        else:
            if not isinstance(result, str):
                authority.mark_uncertain(project_id, seal, decision["execution_id"])
                raise ExposureStop("result_unstored")
            if authority.settle(project_id, seal, decision["execution_id"], result) == "uncertain":
                raise SpendClosed("phase_uncertain")
            return {
                "kind": "settled",
                "execution_id": decision["execution_id"],
                "reserved_microusd": decision["reserved_microusd"],
                "result": result,
            }
    finally:
        _current.reset(token)


def _stop_after_failure(authority, project_id, seal, execution_id):
    with authority._lock:
        project = authority._project(project_id, seal)
        found = authority._execution(project, execution_id)
        if found["status"] == "void":
            return
        if found["sends"] == 0 and found["status"] == "reserved":
            found["status"] = "void"
            found["capability"] = secrets.token_hex(16)
            return
        if found["status"] == "reserved":
            found["status"] = "uncertain"
            found["capability"] = secrets.token_hex(16)
