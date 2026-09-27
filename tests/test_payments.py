from tests.conftest import assert_envelope, auth_headers, booking_row, make_booking, payment_row


def pay(client, headers, booking_id, force_status="SUCCESS", **extra):
    return client.post(
        "/payments",
        json={"booking_id": booking_id, "force_status": force_status, **extra},
        headers=headers,
    )


def test_payment_success_confirms_booking(client, admin, centre):
    headers = auth_headers(client)
    booking_id = make_booking(client, headers, centre)
    resp = pay(client, headers, booking_id, "SUCCESS")
    body = assert_envelope(resp.json(), True, 201)
    assert body["data"]["status"] == "SUCCESS"
    assert body["data"]["booking_status"] == "CONFIRMED"
    assert body["data"]["amount"] == 500.0
    assert booking_row(booking_id).status == "CONFIRMED"


def test_payment_failed_fails_booking(client, admin, centre):
    headers = auth_headers(client)
    booking_id = make_booking(client, headers, centre)
    resp = pay(client, headers, booking_id, "FAILED")
    body = assert_envelope(resp.json(), True, 201)
    assert body["data"]["status"] == "FAILED"
    assert body["data"]["booking_status"] == "FAILED"
    assert booking_row(booking_id).status == "FAILED"


def test_payment_unknown_booking(client, admin, centre):
    headers = auth_headers(client)
    resp = pay(client, headers, 9999)
    assert resp.json()["error"]["code"] == "BOOKING_NOT_FOUND"


def test_payment_other_users_booking_forbidden(client, admin, centre):
    owner = auth_headers(client, "owner@test.com")
    stranger = auth_headers(client, "stranger@test.com")
    booking_id = make_booking(client, owner, centre)
    resp = pay(client, stranger, booking_id)
    assert resp.json()["error"]["code"] == "BOOKING_NOT_OWNED"


def test_repeat_payment_rejected(client, admin, centre):
    headers = auth_headers(client)
    booking_id = make_booking(client, headers, centre)
    pay(client, headers, booking_id, "SUCCESS")
    resp = pay(client, headers, booking_id, "SUCCESS")
    body = assert_envelope(resp.json(), False, 409)
    assert body["error"]["code"] == "BOOKING_NOT_PENDING"


def test_payment_on_cancelled_booking_rejected(client, admin, centre):
    headers = auth_headers(client)
    booking_id = make_booking(client, headers, centre)
    client.post(f"/bookings/{booking_id}/cancel", headers=headers)
    resp = pay(client, headers, booking_id)
    assert resp.json()["error"]["code"] == "BOOKING_NOT_PENDING"


def test_payment_get_by_owner(client, admin, centre):
    headers = auth_headers(client)
    booking_id = make_booking(client, headers, centre)
    created = pay(client, headers, booking_id, "SUCCESS").json()["data"]
    resp = client.get(f"/payments/{created['payment_id']}", headers=headers)
    body = assert_envelope(resp.json(), True, 200)
    assert body["data"]["status"] == "SUCCESS"
    assert len(body["data"]["provider_reference"]) == 32


def test_payment_get_by_stranger_forbidden(client, admin, centre):
    owner = auth_headers(client, "owner@test.com")
    stranger = auth_headers(client, "stranger@test.com")
    booking_id = make_booking(client, owner, centre)
    created = pay(client, owner, booking_id, "SUCCESS").json()["data"]
    resp = client.get(f"/payments/{created['payment_id']}", headers=stranger)
    assert resp.json()["error"]["code"] == "BOOKING_NOT_OWNED"


def test_webhook_mode_leaves_payment_pending(client, admin, centre):
    headers = auth_headers(client)
    booking_id = make_booking(client, headers, centre)
    resp = pay(client, headers, booking_id, "SUCCESS", mode="webhook")
    body = assert_envelope(resp.json(), True, 201)
    assert body["data"]["status"] == "PENDING"
    payment_id = body["data"]["id"]
    assert payment_row(payment_id).status == "PENDING"
    assert booking_row(booking_id).status == "PENDING"

    final = None
    import time

    for _ in range(40):
        time.sleep(0.2)
        state = booking_row(booking_id).status
        if state != "PENDING":
            final = state
            break
    assert final == "CONFIRMED"
    assert payment_row(payment_id).status == "SUCCESS"


def test_random_default_is_valid_status(client, admin, centre):
    headers = auth_headers(client)
    booking_id = make_booking(client, headers, centre)
    resp = pay(client, headers, booking_id)
    data = resp.json()["data"]
    assert data["status"] in ("SUCCESS", "FAILED")
    expected = "CONFIRMED" if data["status"] == "SUCCESS" else "FAILED"
    assert data["booking_status"] == expected
