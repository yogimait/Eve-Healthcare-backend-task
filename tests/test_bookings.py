from tests.conftest import appointment, assert_envelope, auth_headers, make_booking


def test_booking_success_price_from_db(client, admin, centre):
    headers = auth_headers(client)
    resp = client.post(
        "/bookings",
        json={
            "centre_id": centre["centre_id"],
            "test_id": centre["test_id"],
            "appointment": appointment(),
        },
        headers=headers,
    )
    body = assert_envelope(resp.json(), True, 201)
    data = body["data"]
    assert data["status"] == "PENDING"
    assert data["amount"] == 500.0
    assert data["centre_name"] == "EVE Delhi"
    assert data["test_name"] == "CBC"


def test_booking_unknown_centre(client, admin, centre):
    headers = auth_headers(client)
    resp = client.post(
        "/bookings",
        json={"centre_id": 9999, "test_id": centre["test_id"], "appointment": appointment()},
        headers=headers,
    )
    body = assert_envelope(resp.json(), False, 404)
    assert body["error"]["code"] == "CENTRE_NOT_FOUND"


def test_booking_unknown_test(client, admin, centre):
    headers = auth_headers(client)
    resp = client.post(
        "/bookings",
        json={"centre_id": centre["centre_id"], "test_id": 9999, "appointment": appointment()},
        headers=headers,
    )
    assert resp.json()["error"]["code"] == "TEST_NOT_FOUND"


def test_booking_test_not_offered_at_centre(client, admin, centre):
    headers = auth_headers(client)
    resp = client.post("/admin/tests", json={"name": "MRI"}, headers=admin["headers"])
    mri_id = resp.json()["data"]["id"]
    resp = client.post(
        "/bookings",
        json={"centre_id": centre["centre_id"], "test_id": mri_id, "appointment": appointment()},
        headers=headers,
    )
    body = assert_envelope(resp.json(), False, 409)
    assert body["error"]["code"] == "TEST_NOT_AVAILABLE"


def test_booking_past_appointment(client, admin, centre):
    headers = auth_headers(client)
    resp = client.post(
        "/bookings",
        json={"centre_id": centre["centre_id"], "test_id": centre["test_id"], "appointment": "2020-01-01T10:00:00Z"},
        headers=headers,
    )
    body = assert_envelope(resp.json(), False, 422)
    assert body["error"]["code"] == "INVALID_APPOINTMENT"


def test_booking_slot_conflict(client, admin, centre):
    headers = auth_headers(client)
    slot = appointment()
    payload = {"centre_id": centre["centre_id"], "test_id": centre["test_id"], "appointment": slot}
    first = client.post("/bookings", json=payload, headers=headers)
    assert first.status_code == 201
    second = client.post("/bookings", json=payload, headers=headers)
    body = assert_envelope(second.json(), False, 409)
    assert body["error"]["code"] == "SLOT_UNAVAILABLE"


def test_slot_freed_after_cancel(client, admin, centre):
    headers = auth_headers(client)
    slot = appointment()
    payload = {"centre_id": centre["centre_id"], "test_id": centre["test_id"], "appointment": slot}
    booking_id = client.post("/bookings", json=payload, headers=headers).json()["data"]["id"]
    client.post(f"/bookings/{booking_id}/cancel", headers=headers)
    resp = client.post("/bookings", json=payload, headers=headers)
    assert resp.status_code == 201


def test_booking_list_only_own(client, admin, centre):
    user_a = auth_headers(client, "a@test.com")
    user_b = auth_headers(client, "b@test.com")
    make_booking(client, user_a, centre)
    resp = client.get("/bookings", headers=user_b)
    body = assert_envelope(resp.json(), True, 200)
    assert body["data"]["total"] == 0
    resp = client.get("/bookings", headers=user_a)
    assert resp.json()["data"]["total"] == 1


def test_booking_access_other_user_forbidden(client, admin, centre):
    owner = auth_headers(client, "owner@test.com")
    stranger = auth_headers(client, "stranger@test.com")
    booking_id = make_booking(client, owner, centre)
    resp = client.get(f"/bookings/{booking_id}", headers=stranger)
    body = assert_envelope(resp.json(), False, 403)
    assert body["error"]["code"] == "BOOKING_NOT_OWNED"


def test_booking_owner_can_view(client, admin, centre):
    headers = auth_headers(client)
    booking_id = make_booking(client, headers, centre)
    resp = client.get(f"/bookings/{booking_id}", headers=headers)
    assert resp.json()["data"]["id"] == booking_id


def test_admin_can_view_any_booking(client, admin, centre):
    headers = auth_headers(client)
    booking_id = make_booking(client, headers, centre)
    resp = client.get(f"/bookings/{booking_id}", headers=admin["headers"])
    assert resp.json()["data"]["id"] == booking_id


def test_booking_unknown_id(client, admin, centre):
    headers = auth_headers(client)
    resp = client.get("/bookings/9999", headers=headers)
    assert resp.json()["error"]["code"] == "BOOKING_NOT_FOUND"


def test_cancel_pending_booking(client, admin, centre):
    headers = auth_headers(client)
    booking_id = make_booking(client, headers, centre)
    resp = client.post(f"/bookings/{booking_id}/cancel", headers=headers)
    assert resp.json()["data"]["status"] == "CANCELLED"


def test_cancel_twice_rejected(client, admin, centre):
    headers = auth_headers(client)
    booking_id = make_booking(client, headers, centre)
    client.post(f"/bookings/{booking_id}/cancel", headers=headers)
    resp = client.post(f"/bookings/{booking_id}/cancel", headers=headers)
    body = assert_envelope(resp.json(), False, 409)
    assert body["error"]["code"] == "INVALID_STATE_TRANSITION"


def test_admin_endpoints_require_admin(client, admin, centre):
    headers = auth_headers(client)
    resp = client.post("/admin/centres", json={"name": "X", "location": "Y"}, headers=headers)
    body = assert_envelope(resp.json(), False, 403)
    assert body["error"]["code"] == "ADMIN_REQUIRED"


def test_admin_endpoints_without_token(client):
    resp = client.post("/admin/centres", json={"name": "X", "location": "Y"})
    assert resp.status_code == 401


def test_add_same_test_twice_rejected(client, admin, centre):
    resp = client.post(
        f"/admin/centres/{centre['centre_id']}/tests",
        json={"test_id": centre["test_id"], "price": "600.00"},
        headers=admin["headers"],
    )
    body = assert_envelope(resp.json(), False, 409)
    assert body["error"]["code"] == "TEST_ALREADY_OFFERED"


def test_centre_listing_includes_tests_and_prices(client, admin, centre):
    resp = client.get(f"/centres/{centre['centre_id']}")
    body = assert_envelope(resp.json(), True, 200)
    tests = body["data"]["tests"]
    assert len(tests) == 1
    assert tests[0]["name"] == "CBC"
    assert tests[0]["price"] == 500.0
