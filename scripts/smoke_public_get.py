#!/usr/bin/env python3
"""GET-only smoke for the public AI Partner hosts.

Fails when a status, redirect, or required snippet does not match. It never
sends a body. Two hosts with the same build pass the equality check even when
that build is older than this PR. Pass --build EXPECTED to require that id.

--expect-gated checks only two anonymous GETs: /api/engagements and
/api/runs/r_does_not_exist. It does not log in, and it is not the legacy auth
matrix. A pass without that flag is pre-deploy information, not proof that
this PR is deployed.
"""
import argparse
import json
import ssl
import sys
import urllib.error
import urllib.request

HOSTS = (
    "https://ai-partner.up.railway.app",
    "https://74da9def-954d-4df0-9234-04a7301c4740.mtm.sh",
)

TEXT_CHECKS = (
    ("/chat", 200, ("Your first engagement is free", "AI Partner")),
    ("/connect", 200, ("Connect",)),
    ("/get-started.md", 200, ("Your first engagement is free",)),
    ("/demos", 200, ("Maritime", "Keiki", "Orchid")),
)

JSON_UNAUTHORIZED = ("/v1/models", "/mcp")
# Anonymous GETs only. --expect-gated does not cover the signed-key matrix.
GATED_GETS = ("/api/engagements", "/api/runs/r_does_not_exist")


def build_errors(actual, expected):
    if not expected:
        return []
    if actual != expected:
        return [f"build {actual!r} != expected {expected!r}"]
    return []


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(url):
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": "ai-partner-smoke-get"})
    opener = urllib.request.build_opener(NoRedirect, urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    try:
        with opener.open(request, timeout=25) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read(200000)


def header(headers, name):
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return ""


def check_health(status, body):
    errors = []
    if status != 200:
        return [f"health status {status}"]
    try:
        payload = json.loads(body.decode())
    except json.JSONDecodeError:
        return ["health body is not JSON"]
    if payload.get("status") != "ok":
        errors.append(f"health status field {payload.get('status')!r}")
    build = payload.get("build")
    if not isinstance(build, str) or len(build) != 12 or any(ch not in "0123456789abcdef" for ch in build):
        errors.append(f"health build {build!r}")
    sha = payload.get("sha")
    if not isinstance(sha, str):
        errors.append("health sha is missing")
    elif sha and (len(sha) != 40 or any(ch not in "0123456789abcdef" for ch in sha)):
        errors.append(f"health sha {sha!r}")
    return errors


def check_text(status, body, expected, needles):
    errors = []
    if status != expected:
        errors.append(f"status {status}, expected {expected}")
        return errors
    text = body.decode("utf-8", "replace")
    for needle in needles:
        if needle not in text:
            errors.append(f"missing {needle!r}")
    return errors


def check_unauthorized(status, body):
    if status != 401:
        return [f"status {status}, expected 401"]
    try:
        payload = json.loads(body.decode())
    except json.JSONDecodeError:
        return ["401 body is not JSON"]
    code = (payload.get("error") or {}).get("code")
    if code != "unauthorized":
        return [f"error code {code!r}"]
    return []


def smoke_host(origin, expect_gated):
    failures = []
    status, _headers, body = fetch(origin + "/health")
    for error in check_health(status, body):
        failures.append(("/health", error))
    build = ""
    try:
        build = json.loads(body.decode()).get("build") or ""
    except json.JSONDecodeError:
        build = ""

    status, headers, body = fetch(origin + "/")
    location = header(headers, "Location")
    if status != 302 or not str(location).endswith("/chat"):
        failures.append(("/", f"status {status} location {location!r}"))

    for path, expected, needles in TEXT_CHECKS:
        status, _headers, body = fetch(origin + path)
        for error in check_text(status, body, expected, needles):
            failures.append((path, error))

    status, headers, _body = fetch(origin + "/pricing")
    location = header(headers, "Location")
    if status != 301 or not str(location).endswith("/connect"):
        failures.append(("/pricing", f"status {status} location {location!r}"))

    for path in JSON_UNAUTHORIZED:
        status, _headers, body = fetch(origin + path)
        for error in check_unauthorized(status, body):
            failures.append((path, error))

    status, headers, body = fetch(origin + "/demos/maritime/kit.zip")
    if status != 200 or not body.startswith(b"PK") or "zip" not in header(headers, "Content-Type"):
        failures.append(("/demos/maritime/kit.zip", f"status {status} type {header(headers, 'Content-Type')!r} prefix {body[:4]!r}"))

    status, _headers, body = fetch(origin + "/api/catalog")
    if status != 200:
        failures.append(("/api/catalog", f"status {status}"))
    else:
        try:
            groups = json.loads(body.decode()).get("groups")
        except json.JSONDecodeError:
            groups = None
        if not isinstance(groups, list) or not groups:
            failures.append(("/api/catalog", "groups missing"))

    observed = {}
    for path in GATED_GETS:
        observed[path] = fetch(origin + path)[0]
        if expect_gated and observed[path] != 401:
            failures.append((path, f"status {observed[path]}, expected 401 after the gate is deployed"))
    return build, failures, observed


def main(argv):
    parser = argparse.ArgumentParser(description="GET-only public smoke")
    parser.add_argument("hosts", nargs="*", default=list(HOSTS))
    parser.add_argument("--expect-gated", action="store_true", help="Require 401 on the two anonymous legacy GETs. Not a full auth matrix.")
    parser.add_argument("--build", default="", help="Require this 12-hex build id on every host.")
    args = parser.parse_args(argv)
    builds = {}
    failed = False
    label = "pre-deploy informational" if not args.expect_gated else "gated anonymous GETs only"
    print(label)
    for origin in args.hosts:
        build, failures, observed = smoke_host(origin, args.expect_gated)
        builds[origin] = build
        for error in build_errors(build, args.build):
            failures.append(("/health", error))
        print(
            f"{origin} build={build or 'missing'} "
            f"engagements={observed['/api/engagements']} run={observed['/api/runs/r_does_not_exist']}"
        )
        for path, error in failures:
            failed = True
            print(f"FAIL {origin} {path}: {error}")
        if not failures:
            print(f"PASS {origin}")
    values = [item for item in builds.values() if item]
    if len(values) >= 2 and len(set(values)) != 1:
        failed = True
        print(f"FAIL builds differ: {builds}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
