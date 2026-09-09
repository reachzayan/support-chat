from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db import get_engine
from app.redis import get_redis

router = APIRouter()


@router.get("/health")
async def health() -> JSONResponse:
    db_ok = False
    redis_ok = False
    try:
        async with get_engine().connect() as connection:
            await connection.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass
    try:
        await get_redis().ping()
        redis_ok = True
    except Exception:
        pass
    if db_ok and redis_ok:
        return JSONResponse({"status": "ok"})
    return JSONResponse(status_code=503, content={"status": "degraded"})
