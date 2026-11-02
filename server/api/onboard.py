"""Agent onboarding: the playbook, signup, and the skills zip."""
import json

from flask import Blueprint, Response, jsonify, request

from ..get_started import openapi_document, render_get_started, render_llms, skills_zip, valid_email
from ..keys import mint_key
from .access import request_origin

bp = Blueprint("onboard", __name__)

_SIGNUP_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sign up · AI Partner</title>
<link rel="icon" href="/favicon-32.png" sizes="32x32" type="image/png">
<link rel="stylesheet" href="/app.css">
</head>
<body>
<div class="bar"><span style="width:100%"></span></div>
<header class="top">
  <a class="brand" href="/chat"><img class="persona" src="/img/brand/avatar.webp" alt="" width="36" height="36"> AI Partner</a>
  <nav class="links">
    <a href="/chat">Chat</a>
    <a href="/pricing">Pricing</a>
    <a href="/connect">Connect</a>
  </nav>
</header>
<main class="wrap">
  <p class="kicker">Starter · free beta</p>
  <h1>Get an API key.</h1>
  <p class="lede">One Strategy engagement: research brief, cited market analysis, expert panel, the judge's Top 5, maturity score, work chart, 1 harness, and 3 skills. Billing is not live. Submitting the same email again issues a new key and does not show the old one.</p>
  <form id="signup">
    <label class="kicker" for="email">Email</label>
    <input id="email" name="email" type="email" required autocomplete="email">
    <input type="hidden" name="plan" value="starter">
    <div class="row"><button class="send" type="submit">Get key</button></div>
  </form>
  <p id="signup-status" class="status" role="status"></p>
  <pre id="signup-key" hidden></pre>
</main>
<script>
document.getElementById("signup").addEventListener("submit", function (event) {
  event.preventDefault();
  var status = document.getElementById("signup-status");
  var box = document.getElementById("signup-key");
  status.textContent = "Issuing a key.";
  fetch("/api/signup", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({email: document.getElementById("email").value, plan: "starter"})
  }).then(function (res) { return res.json().then(function (data) { return {ok: res.ok, data: data}; }); })
    .then(function (result) {
      if (!result.ok) {
        status.textContent = (result.data.error && result.data.error.message) || "Sign-up did not finish.";
        box.hidden = true;
        return;
      }
      status.textContent = "Copy this key into AI_PARTNER_API_KEY. It is not shown again. Do not commit it.";
      box.hidden = false;
      box.textContent = result.data.key;
    });
});
</script>
<script src="/voice.js"></script>
</body>
</html>
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
    return Response(_SIGNUP_PAGE, mimetype="text/html")


@bp.post("/api/signup")
def signup():
    body = request.get_json(force=True, silent=True) or {}
    email = valid_email(body.get("email"))
    if not email:
        return jsonify({"error": {"code": "bad_email", "message": "Enter an email address."}}), 400
    plan = body.get("plan") or "starter"
    try:
        key = mint_key(email, plan)
    except ValueError:
        return jsonify({"error": {"code": "bad_plan", "message": "Plan must be starter, strategy, or harness."}}), 400
    except RuntimeError:
        return jsonify({"error": {"code": "paused", "message": "Sign-ups are paused."}}), 503
    return jsonify({"key": key, "plan": plan, "email": email})
