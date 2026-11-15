"""Checkout and the Stripe webhook. Both stay off until the three Stripe env vars are set."""
import json

from flask import Blueprint, jsonify, request

from ..billing import StripeError, checkout_fields, payment_from_event, signature_ok, stripe_post, stripe_settings
from ..hostrole import account_role, database_allowed
from ..spendguard import CLOSED

bp = Blueprint("billing", __name__)

DISABLED = {
    "error": {
        "code": "billing_disabled",
        "message": "Stripe checkout is off. Set STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, and STRIPE_PRICE_ID.",
    }
}


def _disabled():
    return jsonify(DISABLED), 503


def _closed():
    return jsonify({"error": {"code": "paid_host_closed", "message": CLOSED["paid_host_closed"]}}), 503


@bp.post("/api/billing/checkout")
def checkout():
    settings = stripe_settings()
    if settings is None:
        return _disabled()
    if account_role() != "authority" or not database_allowed():
        return _closed()
    from ..accounts import AccountsUnavailable
    from ..api.access import public_base
    from ..entitlement import current_user

    try:
        user = current_user()
    except AccountsUnavailable:
        return jsonify({"error": {"code": "accounts_unavailable", "message": CLOSED["accounts_unavailable"]}}), 503
    if user is None:
        return jsonify({"error": {"code": "unauthorized", "message": "Sign in required."}}), 401
    if user["questions_remaining"] > 0:
        return jsonify({
            "error": {
                "code": "free_questions_open",
                "message": "This account still has free questions. Checkout opens after those are used.",
            }
        }), 409
    origin = public_base()
    if not origin:
        return jsonify({
            "error": {
                "code": "billing_disabled",
                "message": "Checkout needs a public host. Set PUBLIC_BASE_URL or open this route from the Railway app.",
            }
        }), 503
    fields = checkout_fields(
        user["id"],
        settings["price"],
        origin + "/chat?checkout=success",
        origin + "/chat?checkout=cancel",
    )
    try:
        session = stripe_post(settings["secret"], fields)
    except StripeError as exc:
        return jsonify({"error": {"code": "stripe_unavailable", "message": str(exc)}}), 502
    return jsonify(session)


@bp.post("/api/billing/webhook")
def webhook():
    settings = stripe_settings()
    if settings is None:
        return _disabled()
    payload = request.get_data() or b""
    if not signature_ok(settings["webhook"], payload, request.headers.get("Stripe-Signature", "")):
        return jsonify({"error": {"code": "bad_signature", "message": "Stripe signature did not verify."}}), 400
    if account_role() != "authority" or not database_allowed():
        return _closed()
    try:
        event = json.loads(payload.decode())
    except (UnicodeError, json.JSONDecodeError):
        return jsonify({"error": {"code": "bad_request", "message": "Stripe event was not JSON."}}), 400
    payment = payment_from_event(event)
    if payment == "ignore":
        return jsonify({"ok": True, "ignored": True})
    if payment == "reject":
        return jsonify({"error": {"code": "bad_request", "message": "Stripe event is missing the account."}}), 400
    if payment["price_id"] != settings["price"]:
        return jsonify({"ok": True, "ignored": True})
    from ..accounts import AccountsUnavailable, record_checkout_payment

    try:
        recorded = record_checkout_payment(
            payment["user_id"],
            payment["event_id"],
            payment["session_id"],
            payment["price_id"],
            payment["amount_total"],
            payment["currency"],
        )
    except AccountsUnavailable:
        return jsonify({"error": {"code": "accounts_unavailable", "message": CLOSED["accounts_unavailable"]}}), 503
    if recorded is None:
        return jsonify({"error": {"code": "unknown_user", "message": "No account matches this checkout."}}), 400
    return jsonify({"ok": True, "duplicate": recorded["duplicate"]})
