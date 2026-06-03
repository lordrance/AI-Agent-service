"""S4.1：OTel GenAI span 辅助（启用/禁用）。"""

from __future__ import annotations

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.infrastructure.trace.genai_otel import (
    ATTR_REQUEST_MODEL,
    genai_span,
    record_llm_usage,
)


@pytest.fixture(scope="module", autouse=True)
def otel_memory_exporter():
    """为 OTel 测试安装内存 exporter（模块级一次）。"""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    yield exporter
    exporter.clear()


def test_genai_span_noop_when_disabled(monkeypatch):
    monkeypatch.setenv("OTEL_ENABLED", "false")
    from app.config import get_settings

    get_settings.cache_clear()
    with genai_span("gen_ai.chat", model="test-model") as span:
        assert span is None
    get_settings.cache_clear()


def test_genai_span_and_usage_attributes(monkeypatch, otel_memory_exporter):
    monkeypatch.setenv("OTEL_ENABLED", "true")
    from app.config import get_settings

    get_settings.cache_clear()
    otel_memory_exporter.clear()

    with genai_span("gen_ai.chat", model="gpt-test"):
        pass
    with genai_span("gen_ai.chat", model="m1") as span:
        record_llm_usage(
            span,
            model_id="m1",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
            finish_reason="stop",
        )

    spans = otel_memory_exporter.get_finished_spans()
    assert spans[0].attributes.get(ATTR_REQUEST_MODEL) == "gpt-test"
    assert spans[-1].attributes.get("gen_ai.usage.input_tokens") == 10
    get_settings.cache_clear()
