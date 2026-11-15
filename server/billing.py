"""Stripe Checkout for the engagement after the free questions are used.

The price id, secret key, and webhook secret come from the environment.
This module does not choose a dollar amount. A missing setting leaves billing off.
"""
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from .chat_send import secret_text

TOLERANCE_SECONDS = 300


class StripeError(RuntimeError):
    pass


def stripe_settings():
    secret = secret_text(os.environ.get("STRIPE_SECRET_KEY"))
    webhook = secret_text(os.environ.get("STRIPE_WEBHOOK_SECRET"))
    price = secret_text(os.environ.get("STRIPE_PRICE_ID"))
    if not secret or not webhook or not price:
        return None
    return {"secret": secret, "webhook": webhook, "price": price}


def checkout_fields(user_id, price_id, success_url, cancel_url):
    return {
        "mode": "payment",
        "client_reference_id": user_id,
        "success_url": success_url,
        "cancel_url": cancel_url,
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": "1",
        "metadata[user_id]": user_id,
        "metadata[price_id]": price_id,
    }


def _stripe_post_network(secret, fields):
    body = urllib.parse.urlencode(fields).encode()
    request = urllib.request.Request(
        "https://api.stripe.com/v1/checkout/sessions",
        data=body,
        method="POST",
        headers={
            "Authorization": "Bearer " + secret,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            parsed = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        message = "Stripe did not open a checkout session."
        try:
            error = json.loads(raw).get("error") or {}
            detail = error.get("message")
            if isinstance(detail, str) and detail and secret not in detail:
                message = detail
        except json.JSONDecodeError:
            pass
        raise StripeError(message) from exc
    if not isinstance(parsed, dict) or not parsed.get("url") or not parsed.get("id"):
        raise StripeError("Stripe did not open a checkout session.")
    return {"id": parsed["id"], "url": parsed["url"]}


stripe_post = _stripe_post_network


def sign_payload(secret, payload, timestamp):
    signed = f"{timestamp}.".encode() + payload
    digest = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def signature_ok(secret, payload, header, now=None):
    if not secret or not isinstance(header, str) or not isinstance(payload, (bytes, bytearray)):
        return False
    parts = {}
    signatures = []
    for item in header.split(","):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key == "v1":
            signatures.append(value)
        else:
            parts[key] = value
    stamp = parts.get("t", "")
    if not stamp.isdigit() or not signatures:
        return False
    now = time.time() if now is None else now
    if abs(now - int(stamp)) > TOLERANCE_SECONDS:
        return False
    expected = hmac.new(secret.encode(), f"{stamp}.".encode() + bytes(payload), hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, candidate) for candidate in signatures)


def _text(value):
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if not text or len(text) > 200:
        return ""
    return text


def _cents(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def payment_from_event(event):
    """Return a payment dict, 'ignore', or 'reject'."""
    if not isinstance(event, dict) or event.get("type") != "checkout.session.completed":
        return "ignore"
    data = event.get("data")
    obj = data.get("object") if isinstance(data, dict) else None
    if not isinstance(obj, dict) or obj.get("payment_status") != "paid":
        return "ignore"
    event_id = _text(event.get("id"))
    metadata = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
    reference = _text(obj.get("client_reference_id"))
    named = _text(metadata.get("user_id"))
    if reference and named and reference != named:
        return "reject"
    user_id = reference or named
    if not event_id or not user_id:
        return "reject"
    return {
        "event_id": event_id,
        "user_id": user_id,
        "session_id": _text(obj.get("id")) or None,
        "price_id": _text(metadata.get("price_id")) or None,
        "amount_total": _cents(obj.get("amount_total")),
        "currency": _text(obj.get("currency")) or None,
    }
