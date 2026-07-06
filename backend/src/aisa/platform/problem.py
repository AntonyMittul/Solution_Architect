import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from aisa.platform.middleware import request_id_var
from aisa.shared.errors import AppError

logger = structlog.get_logger(__name__)

ERROR_TYPE_BASE = "https://api.aisolutionarchitect.dev/errors"
PROBLEM_MEDIA_TYPE = "application/problem+json"


def _problem(
    request: Request, status: int, code: str, title: str, detail: str | None
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type=PROBLEM_MEDIA_TYPE,
        content={
            "type": f"{ERROR_TYPE_BASE}/{code.replace('_', '-')}",
            "title": title,
            "status": status,
            "detail": detail,
            "instance": str(request.url.path),
            "trace_id": request_id_var.get(),
        },
    )


def register_problem_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return _problem(request, exc.status, exc.code, exc.title, exc.detail)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        detail = "; ".join(
            f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}" for err in exc.errors()
        )
        return _problem(request, 422, "validation-error", "Request validation failed", detail)

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("http.unhandled_error", path=request.url.path)
        return _problem(request, 500, "internal-error", "Internal error", None)
