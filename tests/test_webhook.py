import hashlib
import hmac
import json

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.models.payment import Payment
from app.models.subscription import Subscription
from app.services.payment_service import PaymentService

def signed_payload(payload: dict) -> tuple[bytes, str]:
    body = json.dumps(
        payload,
        separators=(",", ":"),
    ).encode()

    signature = hmac.new(
        settings.webhook_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    return body, signature

# Успешный
@pytest.mark.asyncio
async def test_confirmed_payment_creates_payment_and_subscription(
    client,
    db_session,
):
    payload = {
        "payment_id": "payment-001",
        "user_id": 42,
        "amount": 4900,
        "status": "CONFIRMED",
    }

    body, signature = signed_payload(payload)

    response = await client.post(
        "/webhook/payment",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
        },
    )

    assert response.status_code == 200

    assert response.json() == {
        "status": "processed",
        "payment_id": "payment-001",
    }

    payment = await db_session.scalar(
        select(Payment).where(
            Payment.payment_id == "payment-001"
        )
    )

    assert payment is not None
    assert payment.user_id == 42
    assert payment.amount == 4900
    assert payment.status == "CONFIRMED"

    subscription = await db_session.scalar(
        select(Subscription).where(
            Subscription.user_id == 42
        )
    )

    assert subscription is not None
    assert subscription.status == "active"

# Дубль
@pytest.mark.asyncio
async def test_duplicate_webhook_is_idempotent(
    client,
    db_session,
):
    payload = {
        "payment_id": "payment-duplicate",
        "user_id": 42,
        "amount": 4900,
        "status": "CONFIRMED",
    }

    body, signature = signed_payload(payload)

    first_response = await client.post(
        "/webhook/payment",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
        },
    )

    assert first_response.status_code == 200

    subscription = await db_session.scalar(
        select(Subscription).where(
            Subscription.user_id == 42
        )
    )

    original_expires_at = subscription.expires_at

    second_response = await client.post(
        "/webhook/payment",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
        },
    )

    assert second_response.status_code == 200

    assert second_response.json() == {
        "status": "already_processed",
    }

    payment_count = await db_session.scalar(
        select(func.count())
        .select_from(Payment)
        .where(
            Payment.payment_id == "payment-duplicate"
        )
    )

    assert payment_count == 1

    db_session.expire_all()

    subscription = await db_session.scalar(
        select(Subscription).where(
            Subscription.user_id == 42
        )
    )

    assert subscription.expires_at == original_expires_at

# PENDING стутус
@pytest.mark.asyncio
async def test_pending_payment_is_ignored(
    client,
    db_session,
):
    payload = {
        "payment_id": "payment-pending",
        "user_id": 42,
        "amount": 4900,
        "status": "PENDING",
    }

    body, signature = signed_payload(payload)

    response = await client.post(
        "/webhook/payment",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
        },
    )

    assert response.status_code == 200

    assert response.json() == {
        "status": "ignored",
        "reason": "payment_not_confirmed",
    }

    payment = await db_session.scalar(
        select(Payment).where(
            Payment.payment_id == "payment-pending"
        )
    )

    assert payment is None

# Пользователя нет
@pytest.mark.asyncio
async def test_unknown_user_returns_404(
    client,
    db_session,
):
    payload = {
        "payment_id": "payment-unknown",
        "user_id": 999999,
        "amount": 4900,
        "status": "CONFIRMED",
    }

    body, signature = signed_payload(payload)

    response = await client.post(
        "/webhook/payment",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
        },
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": "User not found",
    }

    payment = await db_session.scalar(
        select(Payment).where(
            Payment.payment_id == "payment-unknown"
        )
    )

    assert payment is None

# Не валидная подпись
@pytest.mark.asyncio
async def test_invalid_signature_returns_401(
    client,
):
    response = await client.post(
        "/webhook/payment",
        content=(
            b'{"payment_id":"payment-hack",'
            b'"user_id":42,'
            b'"amount":4900,'
            b'"status":"CONFIRMED"}'
        ),
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Signature": "wrong-signature",
        },
    )

    assert response.status_code == 401

# Подписи нет
@pytest.mark.asyncio
async def test_missing_signature_returns_401(
    client,
):
    response = await client.post(
        "/webhook/payment",
        content=(
            b'{"payment_id":"payment-hack",'
            b'"user_id":42,'
            b'"amount":4900,'
            b'"status":"CONFIRMED"}'
        ),
        headers={
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 401

# Роллбэк (имитируем краш) 
@pytest.mark.asyncio
async def test_transaction_rolls_back_when_subscription_activation_fails(
    client,
    db_session,
    monkeypatch,
):
    async def fail_subscription_activation(
        cls,
        session,
        user_id,
    ):
        raise RuntimeError("Simulated subscription failure")

    monkeypatch.setattr(
        PaymentService,
        "_activate_subscription",
        classmethod(fail_subscription_activation),
    )

    payload = {
        "payment_id": "payment-rollback",
        "user_id": 42,
        "amount": 4900,
        "status": "CONFIRMED",
    }

    body, signature = signed_payload(payload)

    response = await client.post(
        "/webhook/payment",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
        },
    )

    assert response.status_code == 500

    payment = await db_session.scalar(
        select(Payment).where(
            Payment.payment_id == "payment-rollback"
        )
    )

    assert payment is None

    subscription = await db_session.scalar(
        select(Subscription).where(
            Subscription.user_id == 42
        )
    )

    assert subscription is None