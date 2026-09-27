# Data Model

[[Home]] | [[Architecture]] | [[API]]

```mermaid
erDiagram
    users ||--o{ bookings : books
    centres ||--o{ centre_tests : offers
    tests ||--o{ centre_tests : "priced at"
    centre_tests ||--o{ bookings : "booked as"
    bookings ||--o{ payments : "paid by"
    payments ||--o{ webhook_events : "notified via"

    users {
        int id PK
        string email UK
        string full_name
        string password_hash
        bool is_admin
    }
    centres {
        int id PK
        string name
        string location
    }
    tests {
        int id PK
        string name UK
        string description
    }
    centre_tests {
        int id PK
        int centre_id FK
        int test_id FK
        int price_paise
    }
    bookings {
        int id PK
        int user_id FK
        int centre_test_id FK
        datetime appointment
        int amount_paise
        string status
    }
    payments {
        int id PK
        int booking_id FK
        int amount_paise
        string status
        string provider_reference UK
    }
    webhook_events {
        string event_id PK
        int payment_id FK
        dict payload
        string status
        int attempts
        datetime next_retry_at
        string last_error
    }
```

## Design points

- **Price lives on `centre_tests`** — same test, per-centre price. `UNIQUE(centre_id, test_id)`.
- **Money as integer paise** everywhere in the DB; API exposes rupees (`500.00`). No float money.
- **Booking amount is a snapshot** of the centre-test price at booking time — later price changes never alter existing bookings.
- **Timestamps naive UTC**; appointments normalized via `to_utc_naive`.

## State machines

```mermaid
stateDiagram-v2
    [*] --> PENDING : create booking
    PENDING --> CONFIRMED : payment SUCCESS
    PENDING --> FAILED : payment FAILED
    PENDING --> CANCELLED : cancel
    CONFIRMED --> CANCELLED : cancel
    FAILED --> [*]
    CANCELLED --> [*]
```

```mermaid
stateDiagram-v2
    [*] --> PENDING : POST /payments
    PENDING --> SUCCESS
    PENDING --> FAILED
    SUCCESS --> [*]
    FAILED --> [*]
```

```mermaid
stateDiagram-v2
    [*] --> PENDING : webhook received (claimed)
    PENDING --> PROCESSED : applied to payment+booking
    PENDING --> FAILED : unknown payment / transient error (retry)
    FAILED --> PROCESSED : retry success
    FAILED --> PERMANENTLY_FAILED : max attempts (5)
    PENDING --> PERMANENTLY_FAILED : conflict / amount mismatch
```

## Constraints & guards

- Active bookings (`PENDING`/`CONFIRMED`) hold the centre+appointment slot; cancellation frees it. Centre row locked with `FOR UPDATE` on Postgres during booking.
- Cancel is blocked while a payment is `PENDING` for the booking.
- `webhook_events.event_id` PK makes duplicate delivery impossible at the DB level.
- `payments.provider_reference` unique (uuid hex) per attempt.
