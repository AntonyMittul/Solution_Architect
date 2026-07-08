from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from aisa.artifacts.api.router import router as artifacts_router
from aisa.blueprint.api.router import router as blueprint_router
from aisa.exports.api.router import router as exports_router
from aisa.identity.api.auth_router import router as auth_router
from aisa.identity.api.workspace_router import router as workspace_router
from aisa.intake.api.router import router as intake_router
from aisa.integrations.api.router import mcp_server_router, provisioning_router
from aisa.metering.api.router import router as metering_router
from aisa.orchestration.api.router import router as runs_router
from aisa.platform.api.health import router as health_router
from aisa.platform.container import Container
from aisa.platform.middleware import RequestContextMiddleware
from aisa.platform.problem import register_problem_handlers
from aisa.projects.api.router import router as projects_router
from aisa.shared.config import Settings
from aisa.shared.db import check_rls_enforcement
from aisa.shared.logging import configure_logging
from aisa.shared.telemetry import configure_metrics, configure_tracing


def create_app(container: Container | None = None) -> FastAPI:
    """App factory. Pass a prebuilt container (e.g. with fakes) in tests;
    in production the container is built and torn down by the lifespan."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if container is None:
            settings = Settings()
            configure_logging(settings.log_level, json_logs=not settings.is_dev)
            configure_tracing(settings, "aisa-api")
            configure_metrics(settings, "aisa-api")
            app.state.container = Container.build(settings)
            if app.state.container.engine is not None:
                await check_rls_enforcement(app.state.container.engine)
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
    app.include_router(auth_router)
    app.include_router(workspace_router)
    app.include_router(projects_router)
    app.include_router(intake_router)
    app.include_router(blueprint_router)
    app.include_router(artifacts_router)
    app.include_router(exports_router)
    app.include_router(metering_router)
    app.include_router(mcp_server_router)
    app.include_router(provisioning_router)
    app.include_router(runs_router)
    return app


app = create_app()
