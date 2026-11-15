"""Stripe checkout stays off without config, and a bad webhook signature is refused.

These tests do not open Postgres and do not call Stripe.
"""
import json
import time

from server import create_app
from server.billing import payment_from_event, sign_payload


def _enable(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_placeholder_value")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_placeholder_value")
    monkeypatch.setenv("STRIPE_PRICE_ID", "price_test_placeholder")


def test_billing_is_off_until_every_stripe_variable_is_set(monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("STRIPE_PRICE_ID", raising=False)

    def explode(*_args, **_kwargs):
        raise AssertionError("stripe")

    monkeypatch.setattr("server.api.billing.stripe_post", explode)
    client = create_app().test_client()
    for path in ("/api/billing/checkout", "/api/billing/webhook"):
        response = client.post(path, data=b"{}")
        assert response.status_code == 503
        assert response.get_json()["error"]["code"] == "billing_disabled"
    _enable(monkeypatch)
    monkeypatch.delenv("STRIPE_PRICE_ID", raising=False)
    assert client.post("/api/billing/checkout").status_code == 503


def test_webhook_rejects_a_bad_or_stale_signature(monkeypatch):
    _enable(monkeypatch)
    client = create_app().test_client()
    payload = b'{"id":"evt_x","type":"checkout.session.completed"}'
    stale = sign_payload("whsec_test_placeholder_value", payload, int(time.time()) - 3600)
    stale_response = client.post(
        "/api/billing/webhook",
        data=payload,
        headers={"Stripe-Signature": stale, "Content-Type": "application/json"},
    )
    assert stale_response.status_code == 400
    assert stale_response.get_json()["error"]["code"] == "bad_signature"
    forged = sign_payload("whsec_other_secret_value", payload, int(time.time()))
    forged_response = client.post(
        "/api/billing/webhook",
        data=payload,
        headers={"Stripe-Signature": forged, "Content-Type": "application/json"},
    )
    assert forged_response.status_code == 400


def test_a_signed_event_on_a_proxy_does_not_open_checkout(monkeypatch):
    _enable(monkeypatch)
    calls = []
    monkeypatch.setattr("server.api.billing.stripe_post", lambda *args: calls.append(args))
    client = create_app().test_client()
    checkout = client.post("/api/billing/checkout")
    assert checkout.status_code == 503
    assert checkout.get_json()["error"]["code"] == "paid_host_closed"
    assert calls == []
    payload = json.dumps({"id": "evt_proxy", "type": "ping"}).encode()
    signature = sign_payload("whsec_test_placeholder_value", payload, int(time.time()))
    hook = client.post(
        "/api/billing/webhook",
        data=payload,
        headers={"Stripe-Signature": signature, "Content-Type": "application/json"},
    )
    assert hook.status_code == 503
    assert hook.get_json()["error"]["code"] == "paid_host_closed"


def test_payment_from_event_keeps_a_missing_amount_null():
    event = {
        "id": "evt_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_1",
                "payment_status": "paid",
                "client_reference_id": "user_1",
                "metadata": {"user_id": "user_1", "price_id": "price_abc"},
                "currency": "usd",
            }
        },
    }
    payment = payment_from_event(event)
    assert payment["amount_total"] is None
    assert payment["price_id"] == "price_abc"
    event["data"]["object"]["payment_status"] = "unpaid"
    assert payment_from_event(event) == "ignore"
    event["type"] = "charge.refunded"
    assert payment_from_event(event) == "ignore"
