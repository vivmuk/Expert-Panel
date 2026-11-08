"""Application exposure for one server-owned project. Not a provider invoice cap.

5000000 microusd is the worst case reserved before a send. Three is the number
of engagement executions, not the number of stage calls and not the Venice
client's own HTTP retries. Those retries are included in the reservation for
the one execution.

`MemoryAuthority` is an in-process stand-in. It is not shared across hosts,
and a copied file is not this object. HTTP does not install an authority.
Entry points refuse before a socket unless `run_execution` set one for an
offline transport.
"""
import secrets
import threading
from contextvars import ContextVar

from .spendguard import SpendClosed, refuse_paid
from .venice.client import MAX_ATTEMPTS as VENICE_UPSTREAM_TRIES

APPLICATION_CEILING_MICROUSD = 5_000_000
MAX_ENGAGEMENT_ATTEMPTS = 3
UPSTREAM_TRIES = {
    "venice": VENICE_UPSTREAM_TRIES,
    "exa": 1,
    "memory": 1,
    "voice": 1,
    "image": 1,
}

_current = ContextVar("exposure_execution", default=None)


class ExposureStop(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class UncertainOutcome(Exception):
    """The offline transport does not know whether a send landed."""


class OfflineTransport:
    """Canned results only. These methods must not open a socket."""

    def venice(self):
        raise UncertainOutcome()

    def search(self):
        raise UncertainOutcome()

    def recall(self):
        raise UncertainOutcome()

    def remember(self):
        raise UncertainOutcome()

    def voice(self):
        raise UncertainOutcome()

    def image(self):
        raise UncertainOutcome()


def current():
    return _current.get()


def activation_blockers():
    return (
        "no_shared_authority_across_hosts",
        "no_external_monotonic_anchor",
        "http_has_no_authority",
        "provider_invoice_unknown",
    )


def _positive_int(value):
    return not isinstance(value, bool) and isinstance(value, int) and value > 0


def quote(plan):
    """Worst case for one execution, including each service's upstream tries."""
    if not isinstance(plan, list) or not plan:
        raise ExposureStop("price_unknown")
    total = 0
    normalized = []
    seen = set()
    for item in plan:
        if not isinstance(item, dict):
            raise ExposureStop("price_unknown")
        service = item.get("service")
        if service not in UPSTREAM_TRIES:
            raise ExposureStop("service_unknown")
        if service in seen:
            raise ExposureStop("plan_rejected")
        calls = item.get("calls")
        unit = item.get("unit_microusd")
        if not _positive_int(calls) or not _positive_int(unit):
            raise ExposureStop("price_unknown")
        tries = UPSTREAM_TRIES[service]
        reserved = calls * tries * unit
        total += reserved
        normalized.append({
            "service": service,
            "calls": calls,
            "unit_microusd": unit,
            "upstream_tries": tries,
            "reserved_microusd": reserved,
        })
        seen.add(service)
    return total, normalized


class MemoryAuthority:
    """Process-local registry. Two instances are two ceilings, not one store."""

    def __init__(self):
        self._lock = threading.Lock()
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

    def begin(self, project_id, seal, plan, execution_id=None):
        reserved, normalized = quote(plan)
        with self._lock:
            project = self._project(project_id, seal)
            if execution_id is not None:
                if not isinstance(execution_id, str) or not execution_id:
                    raise ExposureStop("execution_rejected")
                found = next((item for item in project["executions"] if item["execution_id"] == execution_id), None)
                if found is None:
                    raise ExposureStop("execution_rejected")
                if found["status"] == "settled":
                    return {
                        "kind": "reuse",
                        "execution_id": execution_id,
                        "result": found["result"],
                        "reserved_microusd": found["reserved_microusd"],
                    }
                raise ExposureStop("attempt_uncertain")
            if any(item["status"] == "uncertain" and not item["reconciled"] for item in project["executions"]):
                raise ExposureStop("project_unreconciled")
            if len(project["executions"]) >= MAX_ENGAGEMENT_ATTEMPTS:
                raise ExposureStop("attempts_exhausted")
            spent = sum(item["reserved_microusd"] for item in project["executions"])
            if spent + reserved > APPLICATION_CEILING_MICROUSD:
                raise ExposureStop("over_cap")
            execution = {
                "execution_id": secrets.token_hex(16),
                "report_id": secrets.token_hex(16),
                "status": "reserved",
                "reconciled": False,
                "reserved_microusd": reserved,
                "services": normalized,
                "result": None,
            }
            project["executions"].append(execution)
            return {
                "kind": "reserved",
                "execution_id": execution["execution_id"],
                "reserved_microusd": reserved,
            }

    def _execution(self, project, execution_id):
        found = next((item for item in project["executions"] if item["execution_id"] == execution_id), None)
        if found is None:
            raise ExposureStop("execution_rejected")
        return found

    def mark_uncertain(self, project_id, seal, execution_id):
        with self._lock:
            project = self._project(project_id, seal)
            found = self._execution(project, execution_id)
            if found["status"] == "uncertain":
                return
            if found["status"] != "reserved":
                raise ExposureStop("attempt_uncertain")
            found["status"] = "uncertain"
            found["result"] = None

    def settle(self, project_id, seal, execution_id, result):
        if not isinstance(result, str):
            raise ExposureStop("result_unstored")
        with self._lock:
            project = self._project(project_id, seal)
            found = self._execution(project, execution_id)
            if found["status"] != "reserved":
                raise ExposureStop("attempt_uncertain")
            found["status"] = "settled"
            found["result"] = result

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
            executions = project["executions"]
            return {
                "engagement_attempts": len(executions),
                "reserved_microusd": sum(item["reserved_microusd"] for item in executions),
                "engagement_attempt_cap_enforced": True,
            }

    def report(self, project_id, seal):
        with self._lock:
            project = self._project(project_id, seal)
            executions = []
            for item in project["executions"]:
                executions.append({
                    "report_id": item["report_id"],
                    "status": item["status"],
                    "reserved_worst_case_microusd": item["reserved_microusd"],
                    "services": [
                        {
                            "service": service["service"],
                            "logical_calls": service["calls"],
                            "upstream_tries_covered": service["upstream_tries"],
                            "reserved_worst_case_microusd": service["reserved_microusd"],
                        }
                        for service in item["services"]
                    ],
                    "provider_reported_usage": None,
                    "billed_microusd": None,
                })
            reserved = sum(item["reserved_microusd"] for item in project["executions"])
        return {
            "label": "application_exposure",
            "runtime_enforcement": False,
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
                "provider_invoice_unknown",
                "store_is_process_local",
                "no_external_monotonic_anchor",
            ],
            "executions": executions,
        }


class _Active:
    def __init__(self, authority, project_id, seal, execution_id, plan, transport):
        self.authority = authority
        self.project_id = project_id
        self.seal = seal
        self.execution_id = execution_id
        self.transport = transport
        self.remaining = {item["service"]: item["calls"] for item in plan}
        self.sent = 0

    def consume(self, service):
        left = self.remaining.get(service, 0)
        if left <= 0:
            self.authority.mark_uncertain(self.project_id, self.seal, self.execution_id)
            raise SpendClosed("paid_path_blocked")
        self.remaining[service] = left - 1
        self.sent += 1
        return self.transport


def run_execution(authority, project_id, seal, plan, transport, work, execution_id=None):
    """Reserve the execution, then run work. A non-offline transport never starts."""
    if not isinstance(authority, MemoryAuthority) or not isinstance(transport, OfflineTransport):
        refuse_paid()
    if _current.get() is not None:
        raise ExposureStop("nested_execution")
    decision = authority.begin(project_id, seal, plan, execution_id=execution_id)
    if decision["kind"] == "reuse":
        return decision
    active = _Active(authority, project_id, seal, decision["execution_id"], quote(plan)[1], transport)
    token = _current.set(active)
    try:
        result = work()
    except UncertainOutcome:
        authority.mark_uncertain(project_id, seal, decision["execution_id"])
        raise SpendClosed("phase_uncertain")
    except Exception:
        if active.sent:
            authority.mark_uncertain(project_id, seal, decision["execution_id"])
        else:
            _drop_unsent(authority, project_id, seal, decision["execution_id"])
        raise
    else:
        if not isinstance(result, str):
            authority.mark_uncertain(project_id, seal, decision["execution_id"])
            raise ExposureStop("result_unstored")
        authority.settle(project_id, seal, decision["execution_id"], result)
        return {
            "kind": "settled",
            "execution_id": decision["execution_id"],
            "reserved_microusd": decision["reserved_microusd"],
            "result": result,
        }
    finally:
        _current.reset(token)


def _drop_unsent(authority, project_id, seal, execution_id):
    """Nothing was handed to a transport. Dropping this row is not a refund of a send."""
    with authority._lock:
        project = authority._project(project_id, seal)
        project["executions"] = [
            item for item in project["executions"]
            if not (item["execution_id"] == execution_id and item["status"] == "reserved")
        ]
