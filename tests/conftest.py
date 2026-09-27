import hashlib
import hmac
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from uuid import uuid4

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.gettempdir()}/eve_test_{os.getpid()}.db"
os.environ["JWT_SECRET"] = "test-jwt-secret-0123456789abcdef0123456789abcdef"
os.environ["WEBHOOK_SECRET"] = "whsec-test"
os.environ["RETRY_LOOP_ENABLED"] = "false"
os.environ["RATE_LIMIT_AUTH"] = "1000"
os.environ["RATE_LIMIT_PAYMENTS"] = "1000"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Booking, Payment, User, PAYMENT_PENDING
from app.security import hash_password


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def assert_envelope(body: dict, success: bool, status_code: int) -> dict:
    assert body["status"] is success
    assert body["statusCode"] == status_code
    if success:
        assert set(body.keys()) == {"status", "statusCode", "data"}
    else:
        assert set(body.keys()) == {"status", "statusCode", "message", "error"}
        assert "code" in body["error"]
    return body


def signup(client: TestClient, email: str = "u1@test.com", password: str = "password123", full_name: str = "User One"):
    return client.post("/auth/signup", json={"full_name": full_name, "email": email, "password": password})


def login(client: TestClient, email: str = "u1@test.com", password: str = "password123"):
    return client.post("/auth/login", json={"email": email, "password": password})


def auth_headers(client: TestClient, email: str = "u1@test.com", password: str = "password123") -> dict:
    signup(client, email, password)
    resp = login(client, email, password)
    token = resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin(client: TestClient) -> dict:
    with SessionLocal() as db:
        db.add(
            User(
                email="admin@test.com",
                full_name="Admin",
                password_hash=hash_password("adminpass123"),
                is_admin=True,
            )
        )
        db.commit()
    resp = login(client, "admin@test.com", "adminpass123")
    token = resp.json()["data"]["access_token"]
    return {"headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture
def centre(client: TestClient, admin: dict) -> dict:
    resp = client.post("/admin/centres", json={"name": "EVE Delhi", "location": "Delhi"}, headers=admin["headers"])
    centre_id = resp.json()["data"]["id"]
    resp = client.post(
        "/admin/tests",
        json={"name": "CBC", "description": "Complete Blood Count"},
        headers=admin["headers"],
    )
    test_id = resp.json()["data"]["id"]
    client.post(
        f"/admin/centres/{centre_id}/tests",
        json={"test_id": test_id, "price": "500.00"},
        headers=admin["headers"],
    )
    return {"centre_id": centre_id, "test_id": test_id}


def appointment(days_ahead: int = 3, hour: int = 10) -> str:
    dt = datetime.now(timezone.utc) + timedelta(days=days_ahead)
    dt = dt.replace(hour=hour, minute=0, second=0, microsecond=0)
    return dt.isoformat()


def make_booking(client: TestClient, headers: dict, centre_fixture: dict) -> int:
    resp = client.post(
        "/bookings",
        json={
            "centre_id": centre_fixture["centre_id"],
            "test_id": centre_fixture["test_id"],
            "appointment": appointment(),
        },
        headers=headers,
    )
    return resp.json()["data"]["id"]


def make_pending_payment(booking_id: int, amount_paise: int) -> int:
    with SessionLocal() as db:
        payment = Payment(
            booking_id=booking_id,
            amount_paise=amount_paise,
            status=PAYMENT_PENDING,
            provider_reference=uuid4().hex,
        )
        db.add(payment)
        db.commit()
        return payment.id


def booking_row(booking_id: int) -> Booking:
    with SessionLocal() as db:
        return db.get(Booking, booking_id)


def payment_row(payment_id: int) -> Payment:
    with SessionLocal() as db:
        return db.get(Payment, payment_id)


def count(model) -> int:
    with SessionLocal() as db:
        return len(db.query(model).all())


def webhook_post(client: TestClient, payload: dict, secret: str = "whsec-test"):
    raw = json.dumps(payload).encode()
    signature = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return client.post("/payments/webhook", content=raw, headers={"X-Webhook-Signature": signature})
