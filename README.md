# Payment Webhook Service

A payment webhook service built with **FastAPI**, **PostgreSQL**, **SQLAlchemy**, and **Alembic**.

The service processes subscription payments while guaranteeing:

- webhook authenticity verification;
- idempotent payment processing;
- atomic payment and subscription updates;
- protection against duplicate webhook delivery;
- automatic rollback on processing failures.

---

# Tech Stack

- Python 3.12
- FastAPI
- PostgreSQL 17
- SQLAlchemy 2
- Alembic
- asyncpg
- Pydantic
- Docker & Docker Compose
- pytest
- pytest-asyncio
- HTTPX

---

# Architecture

```text
           Bank / Payment Provider
                     │
                     │ POST /webhook/payment
                     ▼
          HMAC Signature Verification
                     │
                     ▼
           Pydantic Request Validation
                     │
                     ▼
               PaymentService
                     │
          PostgreSQL Transaction
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
    payments               subscriptions
        │                         │
        └────────── COMMIT ───────┘
```

---

# Webhook

### Endpoint

```http
POST /webhook/payment
```

### Payload

```json
{
  "payment_id": "abc-123",
  "user_id": 42,
  "amount": 4900,
  "status": "CONFIRMED"
}
```

Every request must contain an HMAC-SHA256 signature.

```http
X-Webhook-Signature: <signature>
```

The signature is calculated from the **raw HTTP request body** using the shared `WEBHOOK_SECRET`.

> In a real payment-provider integration, the provider's official webhook verification mechanism should be used instead.

---

# Processing Logic

Only payments with

```text
status = CONFIRMED
```

are processed.

Processing is performed inside a **single PostgreSQL transaction**.

```text
BEGIN

Validate user

INSERT payment
ON CONFLICT DO NOTHING

Duplicate?
    YES → return already_processed

UPSERT subscription
status = active
expires_at = now() + 30 days

COMMIT
```

---

# Idempotency

`payments.payment_id` has a **UNIQUE** constraint.

Payments are inserted using PostgreSQL's native conflict handling:

```sql
ON CONFLICT (payment_id) DO NOTHING
```

If the payment provider sends the same webhook multiple times:

- only the first request inserts the payment;
- the subscription is activated only once;
- subsequent requests return:

```json
{
  "status": "already_processed"
}
```

without extending the subscription again.

---

# Atomicity

Payment creation and subscription activation are executed inside **one database transaction**.

```text
BEGIN
    INSERT payment
    UPDATE subscription
COMMIT
```

If an error occurs after the payment is inserted but before the subscription is updated:

```text
BEGIN
    INSERT payment
    ERROR
ROLLBACK
```

the entire transaction is rolled back.

This guarantees that the database never reaches the following inconsistent state:

```text
✓ payment exists
✗ subscription missing
```

If the payment provider retries the webhook, processing continues safely.

---

# Webhook Authentication

The endpoint is public, therefore incoming requests are authenticated using **HMAC-SHA256**.

The service:

1. Reads the raw request body.
2. Calculates the HMAC signature using `WEBHOOK_SECRET`.
3. Compares signatures using `hmac.compare_digest()`.

For production integrations, this mechanism should be replaced with the official signature verification process provided by the payment provider.

---

# Running

Create the environment file:

```bash
cp .env.example .env
```

Start the application:

```bash
docker compose up --build
```

Apply database migrations:

```bash
docker compose run --rm api uv run alembic upgrade head
```

---

## Available endpoints

API

```text
http://localhost:8000
```

Swagger UI

```text
http://localhost:8000/docs
```

Health Check

```text
http://localhost:8000/health
```

---

# Example Webhook

Generate a signature:

```bash
printf '%s' '{"payment_id":"payment-001","user_id":42,"amount":4900,"status":"CONFIRMED"}' \
| openssl dgst -sha256 -hmac "dev-webhook-secret"
```

Send the webhook:

```bash
curl -i \
  -X POST http://localhost:8000/webhook/payment \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: <signature>" \
  -d '{"payment_id":"payment-001","user_id":42,"amount":4900,"status":"CONFIRMED"}'
```

---

# Running Tests

Integration tests use a separate PostgreSQL database.

Start the test database:

```bash
docker compose up -d db_test
```

Run all tests:

```bash
docker compose run --rm api uv run pytest -v
```

Current result:

```text
7 passed
```

Covered scenarios:

- confirmed payment creates payment and subscription;
- duplicate webhook is idempotent;
- non-confirmed payment is ignored;
- unknown user returns **404**;
- invalid webhook signature returns **401**;
- missing webhook signature returns **401**;
- transaction rollback prevents partial database state.

---

# SQL Task

`query.sql` contains the SQL query requested in the assignment:

> Return users with an active subscription who have no attendance records during the last 30 days.

The query assumes that the following table already exists:

```text
meetings_attendance(user_id, date)
```

---

# Design Decisions

### PostgreSQL as the source of truth

Both payments and subscriptions are stored in PostgreSQL to guarantee transactional consistency.

### Database-level idempotency

Instead of checking

```text
SELECT
↓

INSERT
```

the service relies on PostgreSQL:

```sql
ON CONFLICT (payment_id) DO NOTHING
```

which eliminates race conditions.

### Atomic updates

Payment creation and subscription activation are executed inside a single transaction.

This guarantees that either both operations succeed or both are rolled back.

### Webhook authentication

Incoming webhooks are authenticated using HMAC-SHA256.

In production this mechanism should be replaced with the official verification protocol of the chosen payment provider.

### Subscription duration

A confirmed payment activates the subscription for **30 days** from the processing time.

---

# Time Spent

Approximately 3 hours, including:

- project setup;
- FastAPI & SQLAlchemy configuration;
- Docker environment;
- Alembic migrations;
- webhook implementation;
- HMAC authentication;
- integration tests;
- debugging;
- project documentation.