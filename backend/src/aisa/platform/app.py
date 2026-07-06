from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from aisa.orchestration.api.router import router as runs_router
from aisa.platform.api.health import router as health_router
from aisa.platform.container import Container
from aisa.platform.middleware import RequestContextMiddleware
from aisa.platform.problem import register_problem_handlers
from aisa.shared.config import Settings
from aisa.shared.logging import configure_logging


def create_app(container: Container | None = None) -> FastAPI:
    """App factory. Pass a prebuilt container (e.g. with fakes) in tests;
    in production the container is built and torn down by the lifespan."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if container is None:
            settings = Settings()
            configure_logging(settings.log_level, json_logs=not settings.is_dev)
            app.state.container = Container.build(settings)
            try:
                yield
            finally:
                await app.state.container.aclose()
        else:
            yield

    app = FastAPI(title="AI Solution Architect API", version="0.1.0", lifespan=lifespan)
    if container is not None:
        app.state.container = container

    app.add_middleware(RequestContextMiddleware)
    register_problem_handlers(app)
    app.include_router(health_router)
    app.include_router(runs_router)
    return app


app = create_app()
