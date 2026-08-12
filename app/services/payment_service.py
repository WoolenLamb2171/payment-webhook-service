from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.payment import PaymentStatus, PaymentWebhook


class UserNotFoundError(Exception):
    pass


class PaymentService:
    @staticmethod
    async def process_payment(
        session: AsyncSession,
        payload: PaymentWebhook,
    ) -> dict:
        if payload.status != PaymentStatus.CONFIRMED:
            return {
                "status": "ignored",
                "reason": "payment_not_confirmed",
            }

        async with session.begin():
            user = await session.scalar(
                select(User).where(User.id == payload.user_id)
            )

            if user is None:
                raise UserNotFoundError

            payment_statement = (
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

            result = await session.execute(payment_statement)
            created_payment_id = result.scalar_one_or_none()

            if created_payment_id is None:
                return {
                    "status": "already_processed",
                }

            expires_at = datetime.now(timezone.utc) + timedelta(days=30)

            subscription_statement = (
                insert(Subscription)
                .values(
                    user_id=payload.user_id,
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

            await session.execute(subscription_statement)

        return {
            "status": "processed",
            "payment_id": payload.payment_id,
        }