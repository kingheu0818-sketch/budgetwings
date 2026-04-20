from __future__ import annotations

import json
from pathlib import Path

from observability.tracer import LLMTracer


def test_local_json_fallback_records_trace(tmp_path: Path) -> None:
    tracer = LLMTracer(traces_dir=tmp_path)

    trace_id = tracer.start_trace("test-trace", {"city": "深圳"})
    span_id = tracer.start_span(trace_id, "test-span", {"input": "hello"})
    tracer.end_span(
        span_id,
        output_data={"output": "world"},
        token_usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        duration_ms=12.5,
    )
    tracer.end_trace(trace_id, "success", {"deal_count": 1})

    trace_files = list(tmp_path.glob("trace_*.json"))
    assert len(trace_files) == 1
    payload = json.loads(trace_files[0].read_text(encoding="utf-8"))
    assert payload["id"] == trace_id
    assert payload["status"] == "success"
    assert payload["spans"][0]["name"] == "test-span"
    assert payload["spans"][0]["token_usage"]["total_tokens"] == 3


def test_tracer_without_langfuse_config_does_not_raise(tmp_path: Path) -> None:
    tracer = LLMTracer(public_key=None, secret_key=None, traces_dir=tmp_path)

    trace_id = tracer.start_trace("no-remote", {})
    span_id = tracer.start_span(trace_id, "span", {"safe": True})
    tracer.end_span(span_id, {"ok": True}, None, 1.0)
    tracer.end_trace(trace_id, "success", "done")

    assert list(tmp_path.glob("trace_*.json"))
