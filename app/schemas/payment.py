from enum import StrEnum

from pydantic import BaseModel, Field


class PaymentStatus(StrEnum):
    CONFIRMED = "CONFIRMED"
    PENDING = "PENDING"
    FAILED = "FAILED"


class PaymentWebhook(BaseModel):
    payment_id: str = Field(min_length=1, max_length=255)
    user_id: int = Field(gt=0)
    amount: int = Field(gt=0)
    status: PaymentStatus


class PaymentWebhookResponse(BaseModel):
    status: str
    payment_id: str | None = None
    reason: str | None = None