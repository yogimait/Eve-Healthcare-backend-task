# API

[[Home]] | [[Architecture]] | [[Data-Model]]

## Envelope (mandatory)

Success: `{ "status": true, "statusCode": 200, "data": ... }`
Error: `{ "status": false, "statusCode": 4xx, "message": "...", "error": { "code": "...", "details": ... } }`

`statusCode` always equals the HTTP status. Helpers: `app/http.py` `ok()`/`fail()`.

## Endpoints

| Method & path | Auth | Success | Errors (code) |
| --- | --- | --- | --- |
| `POST /auth/signup` | public, rate-limited | 201 | `EMAIL_TAKEN` 409, `VALIDATION_ERROR` 422 |
| `POST /auth/login` | public, rate-limited | 200 | `INVALID_CREDENTIALS` 401 |
| `GET /centres` | public | 200 | — |
| `GET /centres/{id}` | public | 200 | `CENTRE_NOT_FOUND` 404 |
| `GET /tests` | public | 200 | — |
| `POST /admin/centres` | admin | 201 | `ADMIN_REQUIRED` 403 |
| `POST /admin/tests` | admin | 201 | — |
| `POST /admin/centres/{id}/tests` | admin | 201 | `CENTRE_NOT_FOUND`/`TEST_NOT_FOUND` 404, `TEST_ALREADY_OFFERED` 409 |
| `POST /bookings` | user | 201 | `CENTRE_NOT_FOUND`/`TEST_NOT_FOUND` 404, `TEST_NOT_AVAILABLE` 409, `INVALID_APPOINTMENT` 422, `SLOT_UNAVAILABLE` 409 |
| `GET /bookings` | user (own) | 200 | — |
| `GET /bookings/{id}` | owner/admin | 200 | `BOOKING_NOT_FOUND` 404, `BOOKING_NOT_OWNED` 403 |
| `POST /bookings/{id}/cancel` | owner/admin | 200 | `INVALID_STATE_TRANSITION` 409, `PAYMENT_ALREADY_IN_PROGRESS` 409 |
| `POST /payments` | owner/admin, rate-limited | 201 | `BOOKING_NOT_FOUND` 404, `BOOKING_NOT_OWNED` 403, `BOOKING_NOT_PENDING` 409, `PAYMENT_ALREADY_IN_PROGRESS` 409 |
| `GET /payments/{id}` | owner/admin | 200 | `PAYMENT_NOT_FOUND` 404, `BOOKING_NOT_OWNED` 403 |
| `POST /payments/webhook` | HMAC `X-Webhook-Signature` | 200 | `WEBHOOK_INVALID_SIGNATURE` 401, `VALIDATION_ERROR` 422 |

## Key payloads

Login response data:

```json
{ "access_token": "...", "token_type": "bearer", "expires_in": 86400 }
```

Booking data:

```json
{
  "id": 12, "centre_id": 1, "test_id": 5,
  "centre_name": "EVE Diagnostics Delhi", "test_name": "CBC",
  "appointment": "2026-10-05T04:30:00Z", "amount": 500.0,
  "status": "PENDING", "created_at": "2026-09-27T13:00:00Z"
}
```

Payment result data:

```json
{ "payment_id": 7, "booking_id": 12, "amount": 500.0, "status": "SUCCESS", "booking_status": "CONFIRMED" }
```

Webhook request (HMAC-SHA256 hex of raw body in `X-Webhook-Signature`):

```json
{ "event_id": "evt_abc123", "payment_id": 7, "status": "SUCCESS", "amount": "500.00" }
```

Webhook response data — first delivery: `{"event_id": "...", "processed": true}`; duplicates/conflicts: `{"processed": false, "reason": "ALREADY_PROCESSED | QUEUED_FOR_RETRY | CONFLICTING_STATUS | PAYMENT_NOT_FOUND | AMOUNT_MISMATCH"}`.

List endpoints return `{"items": [...], "total": n}`.

`POST /payments` accepts `force_status` (`SUCCESS`/`FAILED`, deterministic for demos/tests) and `mode` (`direct` default, `webhook` → simulated provider calls the webhook ~1.5s later).

## Error codes

Registered in `app/errors.py` (`ERROR_STATUS` maps code → HTTP status). New codes must be registered there. Full list: `VALIDATION_ERROR, UNAUTHORIZED, INVALID_CREDENTIALS, INVALID_TOKEN, WEBHOOK_INVALID_SIGNATURE, FORBIDDEN, ADMIN_REQUIRED, BOOKING_NOT_OWNED, NOT_FOUND, CENTRE_NOT_FOUND, TEST_NOT_FOUND, BOOKING_NOT_FOUND, PAYMENT_NOT_FOUND, EMAIL_TAKEN, TEST_ALREADY_OFFERED, TEST_NOT_AVAILABLE, SLOT_UNAVAILABLE, INVALID_STATE_TRANSITION, BOOKING_NOT_PENDING, PAYMENT_ALREADY_IN_PROGRESS, INVALID_APPOINTMENT, RATE_LIMITED, INTERNAL_ERROR, NOT_IMPLEMENTED`.
