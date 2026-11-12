"""Agent onboarding: the playbook, signup, and the skills zip."""
import threading
import time

from flask import Blueprint, Response, jsonify, request

from ..get_started import openapi_document, render_get_started, render_llms, skills_zip, valid_email
from ..keys import mint_key
from .access import request_origin
from .chat import client_ip

bp = Blueprint("onboard", __name__)

SIGNUP_WINDOW_SECONDS = 3600
SIGNUP_LIMIT = 5
_signup_lock = threading.Lock()
_signups = {}


def allow_signup(ip, now=None):
    now = time.time() if now is None else now
    with _signup_lock:
        for key in [key for key, stamps in _signups.items() if now - stamps[-1] >= SIGNUP_WINDOW_SECONDS]:
            _signups.pop(key, None)
        stamps = [stamp for stamp in _signups.get(ip, []) if now - stamp < SIGNUP_WINDOW_SECONDS]
        if len(stamps) >= SIGNUP_LIMIT:
            _signups[ip] = stamps
            return False
        _signups[ip] = stamps + [now]
        return True


def reset_signups():
    with _signup_lock:
        _signups.clear()

_SIGNUP_BODY = """<div class="connect-hero">
<section class="page-head">
  <div class="page-head-copy">
    <p class="kicker">Your first engagement is free</p>
    <h1>Get a key for <em>your agent</em>.</h1>
    <p class="lede">The key runs one full engagement from your own agent: a cited research brief, 20 AI experts, a two-round debate, the judge's Top 5, a maturity score, a work chart, 1 harness, and 3 skills. No card.</p>
  </div>
</section>
<form id="signup" class="form-card gb">
  <div class="field">
    <label for="email">Work email</label>
    <input id="email" name="email" type="email" required autocomplete="email" placeholder="you@company.com">
  </div>
  <button class="btn primary" type="submit">__KEY__Get the free key</button>
  <p id="signup-status" class="status-line" role="status"></p>
  <div class="code" id="signup-out" hidden><pre id="signup-key" class="key-out"></pre><button type="button" class="copy" data-copy="signup-key" aria-label="Copy the key">__COPY__<span>Copy</span></button></div>
  <ul class="checklist">
    <li>__CHECK__<span>Put the key in AI_PARTNER_API_KEY. It is shown once.</span></li>
    <li>__CHECK__<span>Submitting the same email again issues a new key and never shows the old one.</span></li>
    <li>__CHECK__<span>Then follow <a href="/connect">Connect</a> for your agent.</span></li>
  </ul>
</form>
</div>
<script>
document.getElementById("signup").addEventListener("submit", function (event) {
  event.preventDefault();
  var status = document.getElementById("signup-status");
  var out = document.getElementById("signup-out");
  var box = document.getElementById("signup-key");
  status.textContent = "Issuing a key.";
  fetch("/api/signup", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({email: document.getElementById("email").value})
  }).then(function (res) { return res.json().then(function (data) { return {ok: res.ok, data: data}; }); })
    .then(function (result) {
      if (!result.ok) {
        status.textContent = (result.data.error && result.data.error.message) || "Sign-up did not finish.";
        out.hidden = true;
        return;
      }
      status.textContent = "Copy this key into AI_PARTNER_API_KEY. It is not shown again. Do not commit it.";
      out.hidden = false;
      box.textContent = result.data.key;
    })
    .catch(function () { status.textContent = "The request failed. Try again."; });
});
</script>
"""


@bp.get("/get-started.md")
def get_started():
    body = render_get_started(request_origin())
    return Response(body, mimetype="text/markdown")


@bp.get("/llms.txt")
def llms_txt():
    return Response(render_llms(request_origin()), mimetype="text/plain")


@bp.get("/openapi.json")
def openapi():
    return jsonify(openapi_document(request_origin()))


@bp.get("/skills.zip")
def skills():
    return Response(skills_zip(), mimetype="application/zip", headers={"Content-Disposition": "attachment; filename=skills.zip"})


@bp.get("/signup")
def signup_page():
    from ..icons import icon
    from .pages import shell

    body = (
        _SIGNUP_BODY.replace("__KEY__", icon("key-round"))
        .replace("__COPY__", icon("copy"))
        .replace("__CHECK__", icon("circle-check"))
    )
    return Response(shell("Get a key · AI Partner", "/connect", body), mimetype="text/html")


@bp.post("/api/signup")
def signup():
    body = request.get_json(force=True, silent=True) or {}
    email = valid_email(body.get("email"))
    if not email:
        return jsonify({"error": {"code": "bad_email", "message": "Enter an email address."}}), 400
    plan = body.get("plan") or "starter"
    if plan != "starter":
        return jsonify({"error": {"code": "bad_plan", "message": "Sign-up issues the free Starter key."}}), 400
    if not allow_signup(client_ip()):
        return jsonify({"error": {"code": "rate", "message": "Too many keys from this network. Try again in an hour."}}), 429
    try:
        key = mint_key(email, plan)
    except RuntimeError:
        return jsonify({"error": {"code": "paused", "message": "Sign-ups are paused."}}), 503
    from ..usage import note_event

    note_event("agent", email, "connect")
    return jsonify({"key": key, "plan": plan, "email": email})
