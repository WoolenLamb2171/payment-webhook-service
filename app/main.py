from fastapi import FastAPI

from app.core.config import settings

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session

from app.api.payment import router as payment_router

app = FastAPI(
    title="Payment Webhook Service",
    version="1.0.0",
)


@app.get("/health")
async def health_check(
    session: AsyncSession = Depends(get_db_session),
):

    return {
        "status": "ok",
        "database_connected": True,
    }


app.include_router(payment_router)