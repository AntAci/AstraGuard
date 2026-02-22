#!/usr/bin/env python3
"""OpenTelemetry tracing bootstrap for Arize Phoenix ingestion."""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Dict, Iterator, Optional


LOGGER = logging.getLogger(__name__)

try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    OTEL_AVAILABLE = True
except Exception:
    OTEL_AVAILABLE = False
    trace = None  # type: ignore[assignment]


_INITIALIZED = False


def _is_enabled() -> bool:
    value = str(os.environ.get("ASTRA_PHOENIX_ENABLED", "false")).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _parse_headers(raw_headers: str) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    for item in raw_headers.split(","):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and value:
            headers[key] = value
    return headers


def _endpoint() -> str:
    endpoint = os.environ.get("PHOENIX_COLLECTOR_ENDPOINT", "").strip()
    if endpoint:
        return endpoint
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "").strip()
    if endpoint:
        return endpoint
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    return endpoint


def init_tracing_if_enabled() -> bool:
    """Initialize global OTel tracer provider when explicitly enabled."""

    global _INITIALIZED
    if _INITIALIZED:
        return True

    if not _is_enabled():
        LOGGER.info("Phoenix tracing disabled (ASTRA_PHOENIX_ENABLED=false)")
        return False

    if not OTEL_AVAILABLE:
        LOGGER.warning("Phoenix tracing enabled but OpenTelemetry dependencies are unavailable")
        return False

    endpoint = _endpoint()
    if not endpoint:
        LOGGER.warning("Phoenix tracing enabled but no OTLP endpoint configured")
        return False

    service_name = os.environ.get("OTEL_SERVICE_NAME", "astragaurd-api")
    headers = _parse_headers(str(os.environ.get("OTEL_EXPORTER_OTLP_HEADERS", "")))

    try:
        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=endpoint, headers=headers)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        _INITIALIZED = True
        LOGGER.info("Phoenix tracing initialized service=%s endpoint=%s", service_name, endpoint)
        return True
    except Exception as err:
        LOGGER.exception("Failed to initialize Phoenix tracing: %s", err)
        return False


class _NoopSpan:
    def set_attribute(self, key: str, value: object) -> None:  # noqa: ARG002
        return None

    def record_exception(self, exception: BaseException) -> None:  # noqa: ARG002
        return None

    def get_span_context(self) -> object:
        class _Ctx:
            trace_id = 0
            span_id = 0

        return _Ctx()


class _NoopTracer:
    @contextmanager
    def start_as_current_span(self, name: str) -> Iterator[_NoopSpan]:  # noqa: ARG002
        yield _NoopSpan()


def get_tracer(name: str):
    if OTEL_AVAILABLE:
        return trace.get_tracer(name)
    return _NoopTracer()


def format_trace_ids(span: object) -> Dict[str, Optional[str]]:
    try:
        span_context = span.get_span_context()  # type: ignore[attr-defined]
        trace_id = int(getattr(span_context, "trace_id", 0))
        span_id = int(getattr(span_context, "span_id", 0))
    except Exception:
        return {"trace_id": None, "span_id": None}

    if trace_id == 0 or span_id == 0:
        return {"trace_id": None, "span_id": None}

    return {
        "trace_id": f"{trace_id:032x}",
        "span_id": f"{span_id:016x}",
    }
