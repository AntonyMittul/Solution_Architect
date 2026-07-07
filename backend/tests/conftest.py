"""Shared pytest setup. Installs an in-memory OpenTelemetry exporter so tracing
instrumentation can be asserted without a collector; the exporter is cleared
before each test."""

from collections.abc import Iterator

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

_EXPORTER = InMemorySpanExporter()

# Set once at import (before app/instrumentation modules resolve the provider).
_provider = TracerProvider()
_provider.add_span_processor(SimpleSpanProcessor(_EXPORTER))
trace.set_tracer_provider(_provider)


@pytest.fixture(autouse=True)
def _clear_spans() -> Iterator[None]:
    _EXPORTER.clear()
    yield


@pytest.fixture
def spans() -> InMemorySpanExporter:
    return _EXPORTER
