from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import SUBSCRIPTION_DURATION
from app.models.payment import Payment
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.payment import PaymentStatus, PaymentWebhook


class UserNotFoundError(Exception):
    pass


class PaymentService:
    @classmethod
    async def process_payment(
        cls,
        session: AsyncSession,
        payload: PaymentWebhook,
    ) -> dict:
        if payload.status != PaymentStatus.CONFIRMED:
            return {
                "status": "ignored",
                "reason": "payment_not_confirmed",
            }

        async with session.begin():
            await cls._validate_user(
                session=session,
                user_id=payload.user_id,
            )

            created_payment_id = await cls._create_payment(
                session=session,
                payload=payload,
            )

            if created_payment_id is None:
                return {
                    "status": "already_processed",
                }

            await cls._activate_subscription(
                session=session,
                user_id=payload.user_id,
            )

        return {
            "status": "processed",
            "payment_id": payload.payment_id,
        }

    @classmethod
    async def _validate_user(
        cls,
        session: AsyncSession,
        user_id: int,
    ) -> None:
        user = await session.scalar(
            select(User).where(User.id == user_id)
        )

        if user is None:
            raise UserNotFoundError

    @classmethod
    async def _create_payment(
        cls,
        session: AsyncSession,
        payload: PaymentWebhook,
    ) -> int | None:
        statement = (
            insert(Payment)
            .values(
                payment_id=payload.payment_id,
                user_id=payload.user_id,
                amount=payload.amount,
                status=payload.status.value,
            )
            .on_conflict_do_nothing(
                index_elements=[Payment.payment_id],
            )
            .returning(Payment.id)
        )

        result = await session.execute(statement)

        return result.scalar_one_or_none()

    @classmethod
    async def _activate_subscription(
        cls,
        session: AsyncSession,
        user_id: int,
    ) -> None:
        expires_at = datetime.now(timezone.utc) + SUBSCRIPTION_DURATION

        statement = (
            insert(Subscription)
            .values(
                user_id=user_id,
                status="active",
                expires_at=expires_at,
            )
            .on_conflict_do_update(
                index_elements=[Subscription.user_id],
                set_={
                    "status": "active",
                    "expires_at": expires_at,
                },
            )
        )

        await session.execute(statement)