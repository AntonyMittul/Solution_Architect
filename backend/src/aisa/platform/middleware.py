import contextvars
import time

import structlog

from aisa.shared.ids import new_id

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

logger = structlog.get_logger("aisa.access")

# Pure ASGI middleware (not BaseHTTPMiddleware) so SSE streaming is untouched.


class RequestContextMiddleware:
    def __init__(self, app):  # type: ignore[no-untyped-def]
        self.app = app

    async def __call__(self, scope, receive, send):  # type: ignore[no-untyped-def]
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = new_id()
        request_id_var.set(request_id)
        structlog.contextvars.bind_contextvars(request_id=request_id)
        start = time.perf_counter()
        status_holder = {"status": 0}

        async def send_wrapper(message):  # type: ignore[no-untyped-def]
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                headers = message.setdefault("headers", [])
                headers.append((b"x-request-id", request_id.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            logger.info(
                "http.request",
                method=scope["method"],
                path=scope["path"],
                status=status_holder["status"],
                duration_ms=duration_ms,
            )
            structlog.contextvars.unbind_contextvars("request_id")
