"""OpenTelemetry tracing setup (doc 14).

Instrumentation across the app uses `get_tracer(...)` and `start_as_current_span`.
Those are cheap no-ops until `configure_tracing` installs a provider, so tracing
is off unless explicitly enabled (AISA_OTEL_ENABLED). In production, set an OTLP
endpoint; in dev, spans print to the console; tests inject an in-memory exporter.
"""

import structlog
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SpanExporter,
)
from opentelemetry.sdk.trace.sampling import ParentBasedTraceIdRatio

from aisa.shared.config import Settings

logger = structlog.get_logger(__name__)


def _select_exporter(settings: Settings) -> SpanExporter | None:
    if settings.otel_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        except ImportError:
            logger.warning(
                "otel.otlp_unavailable",
                detail="install opentelemetry-exporter-otlp-proto-http to use AISA_OTEL_ENDPOINT",
            )
            return None
        otlp: SpanExporter = OTLPSpanExporter(endpoint=settings.otel_endpoint)
        return otlp
    if settings.is_dev:
        return ConsoleSpanExporter()
    return None


def configure_tracing(settings: Settings, service_name: str) -> None:
    if not settings.otel_enabled:
        return
    provider = TracerProvider(
        resource=Resource.create({"service.name": service_name}),
        sampler=ParentBasedTraceIdRatio(settings.otel_sample_ratio),
    )
    exporter = _select_exporter(settings)
    if exporter is not None:
        provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    logger.info("otel.configured", service=service_name, endpoint=settings.otel_endpoint or None)


def get_tracer(name: str) -> trace.Tracer:
    return trace.get_tracer(name)


def current_trace_id() -> str | None:
    """The active trace id as a 32-hex string, for correlating logs with traces."""
    context = trace.get_current_span().get_span_context()
    return format(context.trace_id, "032x") if context.is_valid else None
