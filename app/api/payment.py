from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.webhook_auth import verify_webhook_signature
from app.db.session import get_db_session
from app.schemas.payment import PaymentWebhook
from app.services.payment_service import (
    PaymentService,
    UserNotFoundError,
)


router = APIRouter(
    prefix="/webhook",
    tags=["webhooks"],
)


@router.post(
    "/payment",
    dependencies=[Depends(verify_webhook_signature)],
)
async def payment_webhook(
    payload: PaymentWebhook,
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await PaymentService.process_payment(
            session=session,
            payload=payload,
        )
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )