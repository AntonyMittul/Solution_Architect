from fastapi import APIRouter, Request, Response
from sqlalchemy import text

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request, response: Response) -> dict[str, str]:
    container = request.app.state.container
    checks: dict[str, str] = {}

    if container.engine is not None:
        try:
            async with container.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            checks["postgres"] = "ok"
        except Exception:
            checks["postgres"] = "down"
    if container.redis is not None:
        try:
            await container.redis.ping()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "down"

    if any(v == "down" for v in checks.values()):
        response.status_code = 503
        return {"status": "degraded", **checks}
    return {"status": "ok", **checks}
