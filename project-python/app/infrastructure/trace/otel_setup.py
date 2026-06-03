# -*- coding: utf-8 -*-
"""OpenTelemetry SDK 初始化（可选 OTLP 导出）。"""

from __future__ import annotations

from loguru import logger

from app.config import get_settings


def configure_otel() -> None:
    """启用 OTel 时注册 TracerProvider；配置了 OTLP 端点时导出 span。"""
    settings = get_settings()
    if not settings.otel_enabled:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as exc:
        logger.warning("OTel SDK 未安装，跳过: {}", exc)
        return

    resource = Resource.create({"service.name": settings.otel_service_name})
    provider = TracerProvider(resource=resource)

    endpoint = (settings.otel_exporter_otlp_endpoint or "").strip()
    if endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            exporter = OTLPSpanExporter(endpoint=endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info("OTel OTLP HTTP 导出已启用 endpoint={}", endpoint)
        except ImportError:
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                    OTLPSpanExporter,
                )

                exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
                provider.add_span_processor(BatchSpanProcessor(exporter))
                logger.info("OTel OTLP gRPC 导出已启用 endpoint={}", endpoint)
            except ImportError as exc:
                logger.warning("未安装 OTLP exporter，仅进程内 span: {}", exc)
    else:
        logger.info("OTel 已启用（无 OTLP 端点，span 仅进程内）")

    trace.set_tracer_provider(provider)
