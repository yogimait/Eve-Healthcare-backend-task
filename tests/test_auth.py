from tests.conftest import assert_envelope, login, signup


def test_signup_success(client):
    resp = signup(client)
    body = assert_envelope(resp.json(), True, 201)
    assert body["data"]["email"] == "u1@test.com"
    assert body["data"]["is_admin"] is False
    assert "password" not in body["data"]


def test_signup_duplicate_email(client):
    signup(client)
    resp = signup(client)
    body = assert_envelope(resp.json(), False, 409)
    assert body["error"]["code"] == "EMAIL_TAKEN"


def test_signup_invalid_email(client):
    resp = client.post(
        "/auth/signup", json={"full_name": "X", "email": "not-an-email", "password": "password123"}
    )
    body = assert_envelope(resp.json(), False, 422)
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_signup_short_password(client):
    resp = client.post("/auth/signup", json={"full_name": "X", "email": "a@b.com", "password": "short"})
    assert resp.json()["statusCode"] == 422


def test_login_success(client):
    signup(client)
    resp = login(client)
    body = assert_envelope(resp.json(), True, 200)
    data = body["data"]
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0
    assert data["access_token"].count(".") == 2


def test_login_wrong_password(client):
    signup(client)
    resp = login(client, password="wrongpassword")
    body = assert_envelope(resp.json(), False, 401)
    assert body["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_unknown_email(client):
    resp = login(client, email="ghost@test.com")
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_protected_endpoint_without_token(client):
    resp = client.get("/bookings")
    body = assert_envelope(resp.json(), False, 401)
    assert body["error"]["code"] == "UNAUTHORIZED"


def test_protected_endpoint_invalid_token(client):
    resp = client.get("/bookings", headers={"Authorization": "Bearer garbage"})
    assert resp.json()["error"]["code"] == "INVALID_TOKEN"


def test_health_envelope(client):
    resp = client.get("/health")
    body = assert_envelope(resp.json(), True, 200)
    assert body["data"]["service"] == "eve-backend"


def test_rate_limit(client, monkeypatch):
    from app import rate_limit as rl
    from app.config import settings

    monkeypatch.setattr(settings, "rate_limit_auth", 2)
    rl.clear_rate_limit_store()
    try:
        for _ in range(2):
            resp = login(client, email="rl@test.com")
            assert resp.status_code == 401
        resp = login(client, email="rl@test.com")
        body = assert_envelope(resp.json(), False, 429)
        assert body["error"]["code"] == "RATE_LIMITED"
    finally:
        rl.clear_rate_limit_store()
