"""OpenTelemetry setup and span attribute names."""

from analyst.telemetry import attrs
from analyst.telemetry.setup import (
    TRACER_NAME,
    JsonlFileSpanExporter,
    RunTracing,
)

__all__ = ["TRACER_NAME", "JsonlFileSpanExporter", "RunTracing", "attrs"]
