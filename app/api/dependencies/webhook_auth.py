import hashlib
import hmac
from typing import Annotated

from fastapi import Header, HTTPException, Request, status

from app.core.config import settings


async def verify_webhook_signature(
    request: Request,
    x_webhook_signature: Annotated[str | None, Header()] = None,
) -> None:
    if x_webhook_signature is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing webhook signature",
        )

    body = await request.body()

    expected_signature = hmac.new(
        settings.webhook_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(
        expected_signature,
        x_webhook_signature,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized webhook",
        )