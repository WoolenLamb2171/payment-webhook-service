from fastapi import FastAPI

from app.core.config import settings

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session


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

@app.get("/debug/schema")
async def debug_schema(
    session: AsyncSession = Depends(get_db_session),
):
    query = text("""
        SELECT
            table_name,
            column_name,
            data_type,
            is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position;
    """)

    result = await session.execute(query)

    schema = {}

    for row in result.mappings():
        table = row["table_name"]

        if table not in schema:
            schema[table] = []

        schema[table].append({
            "column": row["column_name"],
            "type": row["data_type"],
            "nullable": row["is_nullable"],
        })

    return schema