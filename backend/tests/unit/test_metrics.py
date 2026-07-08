from opentelemetry import metrics as otel_metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from aisa.shared import metrics


def test_instruments_record_through_a_provider() -> None:
    # Installing a provider upgrades the proxy instruments created at import.
    reader = InMemoryMetricReader()
    otel_metrics.set_meter_provider(MeterProvider(metric_readers=[reader]))

    metrics.record_run_outcome("blueprint", "completed")
    metrics.record_llm_tokens("gemini-3.1-flash-lite", 100, 200)
    metrics.record_http_request("GET", 200, 12.5)

    data = reader.get_metrics_data()
    names = {
        metric.name
        for rm in data.resource_metrics
        for sm in rm.scope_metrics
        for metric in sm.metrics
    }
    assert {"aisa.runs.total", "aisa.llm.tokens.total", "aisa.http.server.duration"} <= names
