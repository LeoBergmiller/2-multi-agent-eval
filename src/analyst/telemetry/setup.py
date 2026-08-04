"""OTel setup with a JSONL file exporter.

architecture.md §8: the file exporter is **always on** and `spans.jsonl` is the
source of truth for scoring. The eval harness reads JSONL only and must never
depend on a SaaS API — so there is no OTLP exporter here. Sampled LangSmith
export lands at Gate 1, as a second exporter alongside this one, never as a
replacement for it.

`SimpleSpanProcessor` is deliberate: `BatchSpanProcessor` would reorder and
delay writes, and the harness reconstructs a trajectory from this file. Ordering
is part of the data, not an implementation detail.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Sequence
from pathlib import Path
from types import TracebackType
from typing import Any, Self

from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)

TRACER_NAME = "analyst"


class JsonlFileSpanExporter(SpanExporter):
    """Appends one JSON object per span to `spans.jsonl`.

    Only the fields the harness needs are written. `parent_span_id` is what lets
    §7.1 rebuild the span *tree* rather than a flat list, so it is emitted even
    when null.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        # Truncate: a run directory describes exactly one run.
        self._path.write_text("")

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        lines = [json.dumps(self._as_record(s), sort_keys=True) for s in spans]
        with self._lock, self._path.open("a") as fh:
            for line in lines:
                fh.write(line + "\n")
        return SpanExportResult.SUCCESS

    @staticmethod
    def _as_record(span: ReadableSpan) -> dict[str, Any]:
        # A span without a context cannot be placed in the tree. That should be
        # impossible for a recorded span, but it is written out with null ids
        # rather than dropped: a missing line would score as a step that never
        # happened, which is a worse failure than a malformed one.
        ctx = span.get_span_context()
        parent = span.parent
        attributes: dict[str, Any] = dict(span.attributes or {})
        return {
            "name": span.name,
            "span_id": format(ctx.span_id, "016x") if ctx else None,
            "trace_id": format(ctx.trace_id, "032x") if ctx else None,
            "parent_span_id": format(parent.span_id, "016x") if parent else None,
            "start_time_ns": span.start_time,
            "end_time_ns": span.end_time,
            "duration_ms": (
                (span.end_time - span.start_time) / 1e6
                if span.end_time and span.start_time
                else None
            ),
            "status": span.status.status_code.name,
            "attributes": attributes,
            "events": [
                {"name": e.name, "attributes": dict(e.attributes or {})}
                for e in span.events
            ],
        }

    def shutdown(self) -> None:  # pragma: no cover - trivial
        return

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return True


class RunTracing:
    """Scopes a `TracerProvider` to one run directory.

    Used as a context manager so the provider is always shut down and the file
    always flushed — a truncated `spans.jsonl` would score as a missing step
    rather than as an error.
    """

    def __init__(self, spans_path: Path) -> None:
        self._exporter = JsonlFileSpanExporter(spans_path)
        self._provider = TracerProvider()
        self._provider.add_span_processor(SimpleSpanProcessor(self._exporter))

    def __enter__(self) -> Self:
        trace.set_tracer_provider(self._provider)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._provider.force_flush()
        self._provider.shutdown()

    @property
    def tracer(self) -> trace.Tracer:
        return self._provider.get_tracer(TRACER_NAME)
