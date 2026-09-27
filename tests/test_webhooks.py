import json
from uuid import uuid4

from app.database import SessionLocal
from app.models import Booking, Payment, WebhookEvent
from tests.conftest import (
    assert_envelope,
    auth_headers,
    booking_row,
    count,
    make_booking,
    make_pending_payment,
    payment_row,
    webhook_post,
)


def base_payload(payment_id: int, status: str = "SUCCESS", amount=None) -> dict:
    payload = {"event_id": f"evt_{uuid4().hex}", "payment_id": payment_id, "status": status}
    if amount is not None:
        payload["amount"] = amount
    return payload


def test_webhook_success_confirms_booking(client, admin, centre):
    headers = auth_headers(client)
    booking_id = make_booking(client, headers, centre)
    payment_id = make_pending_payment(booking_id, 50000)
    resp = webhook_post(client, base_payload(payment_id, "SUCCESS", "500.00"))
    body = assert_envelope(resp.json(), True, 200)
    assert body["data"]["processed"] is True
    assert booking_row(booking_id).status == "CONFIRMED"
    assert payment_row(payment_id).status == "SUCCESS"


def test_webhook_failed_fails_booking(client, admin, centre):
    headers = auth_headers(client)
    booking_id = make_booking(client, headers, centre)
    payment_id = make_pending_payment(booking_id, 50000)
    resp = webhook_post(client, base_payload(payment_id, "FAILED"))
    assert resp.json()["data"]["processed"] is True
    assert booking_row(booking_id).status == "FAILED"


def test_webhook_duplicate_event_is_idempotent(client, admin, centre):
    headers = auth_headers(client)
    booking_id = make_booking(client, headers, centre)
    payment_id = make_pending_payment(booking_id, 50000)
    payload = base_payload(payment_id, "SUCCESS")

    first = webhook_post(client, payload)
    assert first.json()["data"]["processed"] is True

    second = webhook_post(client, payload)
    body = assert_envelope(second.json(), True, 200)
    assert body["data"]["processed"] is False
    assert body["data"]["reason"] == "ALREADY_PROCESSED"

    assert count(Payment) == 1
    assert count(Booking) == 1
    assert booking_row(booking_id).status == "CONFIRMED"
    assert payment_row(payment_id).status == "SUCCESS"
    assert count(WebhookEvent) == 1


def test_webhook_conflicting_status_does_not_corrupt_state(client, admin, centre):
    headers = auth_headers(client)
    booking_id = make_booking(client, headers, centre)
    payment_id = make_pending_payment(booking_id, 50000)
    webhook_post(client, base_payload(payment_id, "SUCCESS"))

    conflict = webhook_post(client, base_payload(payment_id, "FAILED"))
    body = assert_envelope(conflict.json(), True, 200)
    assert body["data"]["processed"] is False

    assert booking_row(booking_id).status == "CONFIRMED"
    assert payment_row(payment_id).status == "SUCCESS"
    with SessionLocal() as db:
        event = db.get(WebhookEvent, body["data"]["event_id"])
        assert event.status == "PERMANENTLY_FAILED"
        assert event.last_error == "CONFLICTING_STATUS"


def test_webhook_second_event_for_final_payment_is_noop(client, admin, centre):
    headers = auth_headers(client)
    booking_id = make_booking(client, headers, centre)
    payment_id = make_pending_payment(booking_id, 50000)
    webhook_post(client, base_payload(payment_id, "SUCCESS"))

    duplicate_result = webhook_post(client, base_payload(payment_id, "SUCCESS"))
    body = assert_envelope(duplicate_result.json(), True, 200)
    assert body["data"]["processed"] is True
    assert booking_row(booking_id).status == "CONFIRMED"


def test_webhook_unknown_payment_queued_for_retry(client, admin, centre):
    payload = base_payload(99999, "SUCCESS")
    resp = webhook_post(client, payload)
    body = assert_envelope(resp.json(), True, 200)
    assert body["data"]["processed"] is False
    assert body["data"]["reason"] == "PAYMENT_NOT_FOUND"

    with SessionLocal() as db:
        event = db.get(WebhookEvent, payload["event_id"])
        assert event.status == "FAILED"
        assert event.next_retry_at is not None


def test_webhook_retry_processes_after_payment_exists(client, admin, centre):
    from app.util import utcnow

    from app.background import process_due_events

    headers = auth_headers(client)
    booking_id = make_booking(client, headers, centre)
    payload = base_payload(99999, "SUCCESS")
    webhook_post(client, payload)

    with SessionLocal() as db:
        event = db.get(WebhookEvent, payload["event_id"])
        event.next_retry_at = utcnow()
        db.commit()
    process_due_events()
    with SessionLocal() as db:
        event = db.get(WebhookEvent, payload["event_id"])
        assert event.status == "FAILED"
        assert event.last_error == "PAYMENT_NOT_FOUND"

    payment_id = make_pending_payment(booking_id, 50000)
    with SessionLocal() as db:
        event = db.get(WebhookEvent, payload["event_id"])
        event.payment_id = payment_id
        event.next_retry_at = utcnow()
        db.commit()

    process_due_events()
    assert payment_row(payment_id).status == "SUCCESS"
    assert booking_row(booking_id).status == "CONFIRMED"
    with SessionLocal() as db:
        assert db.get(WebhookEvent, payload["event_id"]).status == "PROCESSED"


def test_webhook_invalid_signature(client, admin, centre):
    resp = client.post(
        "/payments/webhook",
        content=json.dumps(base_payload(1)).encode(),
        headers={"X-Webhook-Signature": "deadbeef"},
    )
    body = assert_envelope(resp.json(), False, 401)
    assert body["error"]["code"] == "WEBHOOK_INVALID_SIGNATURE"


def test_webhook_missing_signature(client):
    resp = client.post("/payments/webhook", content=b"{}")
    assert resp.status_code == 401


def test_webhook_invalid_status_value(client, admin, centre):
    resp = webhook_post(client, {"event_id": "evt_x", "payment_id": 1, "status": "MAYBE"})
    body = assert_envelope(resp.json(), False, 422)
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_webhook_amount_mismatch_permanently_fails(client, admin, centre):
    headers = auth_headers(client)
    booking_id = make_booking(client, headers, centre)
    payment_id = make_pending_payment(booking_id, 50000)
    resp = webhook_post(client, base_payload(payment_id, "SUCCESS", "999.00"))
    body = assert_envelope(resp.json(), True, 200)
    assert body["data"]["processed"] is False
    assert body["data"]["reason"] == "AMOUNT_MISMATCH"
    with SessionLocal() as db:
        assert db.get(WebhookEvent, body["data"]["event_id"]).status == "PERMANENTLY_FAILED"


def test_webhook_max_attempts_then_permanent(client, admin, centre):
    from app.util import utcnow

    from app.background import process_due_events

    payload = base_payload(99999, "SUCCESS")
    webhook_post(client, payload)
    for _ in range(4):
        with SessionLocal() as db:
            event = db.get(WebhookEvent, payload["event_id"])
            event.next_retry_at = utcnow()
            db.commit()
        process_due_events()
        with SessionLocal() as db:
            event = db.get(WebhookEvent, payload["event_id"])
            if event.attempts < 5:
                assert event.status == "FAILED"
            else:
                assert event.status == "PERMANENTLY_FAILED"
    with SessionLocal() as db:
        event = db.get(WebhookEvent, payload["event_id"])
        assert event.status == "PERMANENTLY_FAILED"
        assert event.attempts == 5


def test_unknown_route_returns_envelope(client):
    resp = client.get("/does-not-exist")
    body = assert_envelope(resp.json(), False, 404)
    assert body["error"]["code"] == "NOT_FOUND"
