from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class LLMTracer:
    def __init__(
        self,
        public_key: str | None = None,
        secret_key: str | None = None,
        host: str = "https://cloud.langfuse.com",
        traces_dir: Path = Path("data/traces"),
    ) -> None:
        self.public_key = public_key
        self.secret_key = secret_key
        self.host = host
        self.traces_dir = traces_dir
        self.current_trace_id: str | None = None
        self._traces: dict[str, dict[str, Any]] = {}
        self._spans: dict[str, dict[str, Any]] = {}
        self._remote: Any | None = self._build_remote_client()

    def start_trace(self, name: str, metadata: dict[str, Any] | None = None) -> str:
        trace_id = str(uuid4())
        self.current_trace_id = trace_id
        trace: dict[str, Any] = {
            "id": trace_id,
            "name": name,
            "metadata": metadata or {},
            "started_at": _now_iso(),
            "finished_at": None,
            "status": "started",
            "summary": None,
            "spans": [],
        }
        self._traces[trace_id] = trace
        if self._remote is not None:
            try:
                self._remote.trace(id=trace_id, name=name, metadata=metadata or {})
            except Exception:
                logger.exception("LangFuse trace start failed; continuing with local trace")
        return trace_id

    def start_span(
        self,
        trace_id: str | None,
        name: str,
        input_data: Any,
    ) -> str:
        resolved_trace_id = trace_id or self.current_trace_id or self.start_trace(
            "ad-hoc",
            {"source": "llm_tracer"},
        )
        span_id = str(uuid4())
        span = {
            "id": span_id,
            "trace_id": resolved_trace_id,
            "name": name,
            "input": input_data,
            "output": None,
            "token_usage": None,
            "duration_ms": None,
            "started_at": _now_iso(),
            "finished_at": None,
        }
        self._spans[span_id] = span
        self._traces.setdefault(
            resolved_trace_id,
            {
                "id": resolved_trace_id,
                "name": "ad-hoc",
                "metadata": {},
                "started_at": _now_iso(),
                "finished_at": None,
                "status": "started",
                "summary": None,
                "spans": [],
            },
        )["spans"].append(span)
        if self._remote is not None:
            try:
                trace = self._remote.trace(id=resolved_trace_id)
                span["_remote"] = trace.span(id=span_id, name=name, input=input_data)
            except Exception:
                logger.exception("LangFuse span start failed; continuing with local trace")
        return span_id

    def end_span(
        self,
        span_id: str,
        output_data: Any,
        token_usage: dict[str, int] | None = None,
        duration_ms: float | None = None,
    ) -> None:
        span = self._spans.get(span_id)
        if span is None:
            return
        span["output"] = output_data
        span["token_usage"] = token_usage
        span["duration_ms"] = duration_ms
        span["finished_at"] = _now_iso()
        remote_span = span.pop("_remote", None)
        if remote_span is not None:
            try:
                remote_span.end(
                    output=output_data,
                    usage=token_usage,
                    metadata={"duration_ms": duration_ms},
                )
            except Exception:
                logger.exception("LangFuse span end failed")

    def end_trace(self, trace_id: str, status: str, summary: dict[str, Any] | str | None) -> None:
        trace = self._traces.get(trace_id)
        if trace is None:
            return
        trace["status"] = status
        trace["summary"] = summary
        trace["finished_at"] = _now_iso()
        if self._remote is not None:
            try:
                self._remote.trace(id=trace_id, metadata={"status": status, "summary": summary})
                self._remote.flush()
            except Exception:
                logger.exception("LangFuse trace end failed; writing local trace")
        self._write_local_trace(trace)
        if self.current_trace_id == trace_id:
            self.current_trace_id = None

    def _build_remote_client(self) -> Any | None:
        if not self.public_key or not self.secret_key:
            return None
        try:
            from langfuse import Langfuse
        except Exception as exc:
            logger.info("LangFuse SDK unavailable; using local JSON traces: %s", exc)
            return None
        try:
            return Langfuse(
                public_key=self.public_key,
                secret_key=self.secret_key,
                host=self.host,
            )
        except Exception:
            logger.exception("LangFuse client init failed; using local JSON traces")
            return None

    def _write_local_trace(self, trace: dict[str, Any]) -> None:
        self.traces_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        path = self.traces_dir / f"trace_{timestamp}_{trace['id']}.json"
        path.write_text(
            json.dumps(_jsonable(trace), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {str(key): _jsonable(item) for key, item in value.items()}
        if isinstance(value, list | tuple):
            return [_jsonable(item) for item in value]
        return repr(value)
