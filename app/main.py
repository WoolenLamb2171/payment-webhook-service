from fastapi import FastAPI

from app.core.config import settings


app = FastAPI(
    title="Payment Webhook Service",
    version="1.0.0",
)


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "database_configured": settings.database_url,
    }