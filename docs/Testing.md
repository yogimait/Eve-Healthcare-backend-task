# Testing

[[Home]] | [[Architecture]] | [[API]]

## Run

```bash
cd python-backend
.venv\Scripts\python -m pytest tests -q
```

52 tests. Tests run on a temp-file SQLite DB (env set in `tests/conftest.py` before app import); Postgres only needed for dev/prod. JWT and webhook secrets are test values set by conftest. The retry loop is disabled (`RETRY_LOOP_ENABLED=false`) so webhook retries are driven deterministically by calling `process_due_events()` directly.

## Layout

- `conftest.py` — fresh schema per test, envelope shape helper (`assert_envelope`), fixtures: `client`, `admin`, `centre`; helpers for bookings, pending payments, signed webhook posts.
- `test_auth.py` — signup/login success, duplicate email, invalid email, short password, wrong credentials, missing/invalid token, health, rate limit.
- `test_bookings.py` — valid booking (price from DB), unknown centre/test, test not offered, past appointment, slot conflict, slot freed after cancel, own-listings, ownership (403), admin access, cancel flows, admin authz, duplicate offer.
- `test_payments.py` — success/failure paths (booking status matches), unknown booking, foreign booking, repeat payment, cancelled booking, `GET /payments/{id}` ownership, webhook mode leaves PENDING then provider confirms, random default validity.
- `test_webhooks.py` — success/failure delivery, **duplicate event idempotency** (counts unchanged), conflicting status never corrupts state, second event on final payment no-op, unknown payment queued for retry, retry after payment exists, max attempts → permanent, bad/missing signature, invalid status, amount mismatch, unknown route envelope.

## Coverage emphasis

Edge cases from the assignment: repeated webhook events, invalid booking IDs, failed payments, unauthorized modifications — each has a dedicated test asserting both the envelope and the database state.
