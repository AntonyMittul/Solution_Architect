import httpx
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic import BaseModel

from aisa.llm.application.service import LLMContext, StructuredLLM
from aisa.llm.infrastructure.fake import FakeLLMProvider
from aisa.llm.infrastructure.usage import NullUsageRecorder
from aisa.platform.app import create_app
from aisa.shared.clock import SystemClock
from tests.helpers import make_walking_skeleton_container


class Answer(BaseModel):
    value: int
    label: str


async def test_llm_complete_emits_span_with_token_attributes(
    spans: InMemorySpanExporter,
) -> None:
    provider = FakeLLMProvider(responses=['{"value": 1, "label": "ok"}'])
    llm = StructuredLLM(provider, NullUsageRecorder())

    await llm.complete(system="s", messages=[], schema=Answer, ctx=LLMContext(run_id="run-123"))

    finished = {s.name: s for s in spans.get_finished_spans()}
    assert "llm.complete" in finished
    attrs = finished["llm.complete"].attributes or {}
    assert attrs["gen_ai.response.model"] == "fake"
    assert attrs["gen_ai.usage.input_tokens"] == 10
    assert attrs["gen_ai.usage.output_tokens"] == 20
    assert attrs["aisa.run_id"] == "run-123"


async def test_http_request_emits_span(spans: InMemorySpanExporter) -> None:
    app = create_app(make_walking_skeleton_container(SystemClock()))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/live")
    assert response.status_code == 200

    finished = {s.name: s for s in spans.get_finished_spans()}
    assert "http.request" in finished
    attrs = finished["http.request"].attributes or {}
    assert attrs["http.request.method"] == "GET"
    assert attrs["url.path"] == "/health/live"
    assert attrs["http.response.status_code"] == 200
