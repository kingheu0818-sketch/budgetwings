from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict

ANTHROPIC_MODELS_TO_PROBE = [
    "claude-sonnet-4-20250514",
    "claude-sonnet-4-5-20250929",
]

OPENAI_MODELS_TO_PROBE = [
    "gpt-5.4",
    "gpt-5.4-mini",
    "claude-sonnet-4-20250514",
]

OUTPUT_DIR = Path("data/probe")
JSON_REPORT_PATH = OUTPUT_DIR / "llm_capability_matrix.json"
MARKDOWN_REPORT_PATH = OUTPUT_DIR / "T4_probe_report.md"
REQUEST_TIMEOUT_SECONDS = 30.0


class ProbeSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    probe_anthropic_base_url: str | None = None
    probe_anthropic_api_key: str | None = None
    probe_openai_base_url: str | None = None
    probe_openai_api_key: str | None = None


@dataclass(frozen=True)
class EndpointConfig:
    provider: str
    base_url: str | None
    api_key: str | None

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    def display_base_url(self) -> str:
        return self.base_url or "not configured"


def normalize_anthropic_base_url(base_url: str) -> str:
    trimmed = base_url.rstrip("/")
    if trimmed.endswith("/v1"):
        return trimmed
    return f"{trimmed}/v1"


def normalize_openai_base_url(base_url: str) -> str:
    trimmed = base_url.rstrip("/")
    if trimmed.endswith("/v1"):
        return trimmed
    return f"{trimmed}/v1"


async def probe_anthropic_model(
    client: httpx.AsyncClient,
    endpoint: EndpointConfig,
    model: str,
) -> dict[str, Any]:
    errors: list[str] = []
    connectivity = await anthropic_connectivity_case(client, endpoint, model)
    errors.extend(connectivity.get("errors", []))
    structured_output = await anthropic_structured_case(client, endpoint, model)
    errors.extend(structured_output.get("errors", []))
    tool_use = await anthropic_tool_use_case(client, endpoint, model)
    errors.extend(tool_use.get("errors", []))
    return {
        "provider": "anthropic",
        "model": model,
        "connectivity": connectivity,
        "structured_output": structured_output,
        "tool_use": tool_use,
        "errors": errors,
    }


async def anthropic_connectivity_case(
    client: httpx.AsyncClient,
    endpoint: EndpointConfig,
    model: str,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "max_tokens": 16,
        "messages": [{"role": "user", "content": "回复一个字:好"}],
    }
    return await anthropic_request_case(client, endpoint, payload, extract_anthropic_text_result)


async def anthropic_structured_case(
    client: httpx.AsyncClient,
    endpoint: EndpointConfig,
    model: str,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "max_tokens": 128,
        "messages": [
            {
                "role": "user",
                "content": (
                    'Return a JSON object: {"city": "Shenzhen", "population": <int>}. '
                    "Only JSON, no explanation."
                ),
            }
        ],
    }
    return await anthropic_request_case(
        client,
        endpoint,
        payload,
        extract_anthropic_structured_result,
    )


async def anthropic_tool_use_case(
    client: httpx.AsyncClient,
    endpoint: EndpointConfig,
    model: str,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "max_tokens": 256,
        "messages": [{"role": "user", "content": "深圳今天天气怎么样?"}],
        "tools": [
            {
                "name": "get_weather",
                "description": "Get current weather for a city.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "Chinese city name, e.g. 深圳",
                        }
                    },
                    "required": ["city"],
                    "additionalProperties": False,
                },
            }
        ],
        "tool_choice": {"type": "tool", "name": "get_weather"},
    }
    return await anthropic_request_case(
        client,
        endpoint,
        payload,
        extract_anthropic_tool_use_result,
    )


async def anthropic_request_case(
    client: httpx.AsyncClient,
    endpoint: EndpointConfig,
    payload: dict[str, Any],
    extractor: Any,
) -> dict[str, Any]:
    url = f"{normalize_anthropic_base_url(endpoint.base_url or '')}/messages"
    headers = {
        "x-api-key": endpoint.api_key or "",
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    started_at = perf_counter()
    try:
        response = await client.post(url, headers=headers, json=payload)
        latency_ms = int((perf_counter() - started_at) * 1000)
        parsed = response.json()
        if response.status_code != 200:
            return {
                "ok": False,
                "http_status": response.status_code,
                "latency_ms": latency_ms,
                "error": extract_error_message(parsed),
                "raw_response": parsed,
                "errors": [f"HTTP {response.status_code}: {extract_error_message(parsed)}"],
            }
        result: dict[str, Any] = dict(extractor(parsed))
        result.update(
            {
                "ok": True,
                "http_status": response.status_code,
                "latency_ms": latency_ms,
                "raw_response": parsed,
                "errors": [],
            }
        )
        return result
    except Exception as exc:
        return {
            "ok": False,
            "http_status": None,
            "latency_ms": None,
            "error": str(exc),
            "raw_response": None,
            "errors": [str(exc)],
        }


def extract_anthropic_text_result(parsed: dict[str, Any]) -> dict[str, Any]:
    text = collect_anthropic_text(parsed)
    return {"sample_output": text}


def extract_anthropic_structured_result(parsed: dict[str, Any]) -> dict[str, Any]:
    text = collect_anthropic_text(parsed)
    stripped = text.strip()
    had_code_fence = stripped.startswith("```") or "```json" in stripped
    valid_json = False
    try:
        json.loads(stripped)
        valid_json = True
    except Exception:
        valid_json = False
    return {
        "valid_json": valid_json,
        "had_code_fence": had_code_fence,
        "raw_response_length": len(text),
        "sample_output": text,
    }


def extract_anthropic_tool_use_result(parsed: dict[str, Any]) -> dict[str, Any]:
    content = parsed.get("content", [])
    tool_called = None
    arguments_valid_json = False
    city_arg = None
    raw_arguments: Any = None
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "tool_use":
            continue
        tool_called = block.get("name")
        raw_arguments = block.get("input")
        if isinstance(raw_arguments, dict):
            arguments_valid_json = True
            city_value = raw_arguments.get("city")
            if isinstance(city_value, str):
                city_arg = city_value
        break
    return {
        "tool_called": tool_called,
        "arguments_valid_json": arguments_valid_json,
        "city_arg": city_arg,
        "raw_arguments": raw_arguments,
    }


def collect_anthropic_text(parsed: dict[str, Any]) -> str:
    parts: list[str] = []
    for block in parsed.get("content", []):
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)


async def probe_openai_model(
    client: httpx.AsyncClient,
    endpoint: EndpointConfig,
    model: str,
) -> dict[str, Any]:
    errors: list[str] = []
    connectivity = await openai_connectivity_case(client, endpoint, model)
    errors.extend(connectivity.get("errors", []))
    structured_output = await openai_structured_case(client, endpoint, model)
    errors.extend(structured_output.get("errors", []))
    tool_use = await openai_tool_use_case(client, endpoint, model)
    errors.extend(tool_use.get("errors", []))
    return {
        "provider": "openai",
        "model": model,
        "connectivity": connectivity,
        "structured_output": structured_output,
        "tool_use": tool_use,
        "errors": errors,
    }


async def openai_connectivity_case(
    client: httpx.AsyncClient,
    endpoint: EndpointConfig,
    model: str,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "回复一个字:好"}],
        "max_tokens": 16,
    }
    return await openai_request_case(client, endpoint, payload, extract_openai_text_result)


async def openai_structured_case(
    client: httpx.AsyncClient,
    endpoint: EndpointConfig,
    model: str,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": (
                    'Return a JSON object: {"city": "Shenzhen", "population": <int>}. '
                    "Only JSON, no explanation."
                ),
            }
        ],
        "max_tokens": 128,
    }
    return await openai_request_case(client, endpoint, payload, extract_openai_structured_result)


async def openai_tool_use_case(
    client: httpx.AsyncClient,
    endpoint: EndpointConfig,
    model: str,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "深圳今天天气怎么样?"}],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get current weather for a city.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {
                                "type": "string",
                                "description": "Chinese city name, e.g. 深圳",
                            }
                        },
                        "required": ["city"],
                        "additionalProperties": False,
                    },
                },
            }
        ],
        "tool_choice": {"type": "function", "function": {"name": "get_weather"}},
        "max_tokens": 128,
    }
    return await openai_request_case(client, endpoint, payload, extract_openai_tool_use_result)


async def openai_request_case(
    client: httpx.AsyncClient,
    endpoint: EndpointConfig,
    payload: dict[str, Any],
    extractor: Any,
) -> dict[str, Any]:
    url = f"{normalize_openai_base_url(endpoint.base_url or '')}/chat/completions"
    headers = {
        "authorization": f"Bearer {endpoint.api_key or ''}",
        "content-type": "application/json",
    }
    started_at = perf_counter()
    try:
        response = await client.post(url, headers=headers, json=payload)
        latency_ms = int((perf_counter() - started_at) * 1000)
        parsed = response.json()
        if response.status_code != 200:
            return {
                "ok": False,
                "http_status": response.status_code,
                "latency_ms": latency_ms,
                "error": extract_error_message(parsed),
                "raw_response": parsed,
                "errors": [f"HTTP {response.status_code}: {extract_error_message(parsed)}"],
            }
        result: dict[str, Any] = dict(extractor(parsed))
        result.update(
            {
                "ok": True,
                "http_status": response.status_code,
                "latency_ms": latency_ms,
                "raw_response": parsed,
                "errors": [],
            }
        )
        return result
    except Exception as exc:
        return {
            "ok": False,
            "http_status": None,
            "latency_ms": None,
            "error": str(exc),
            "raw_response": None,
            "errors": [str(exc)],
        }


def extract_openai_text_result(parsed: dict[str, Any]) -> dict[str, Any]:
    text = collect_openai_text(parsed)
    return {"sample_output": text}


def extract_openai_structured_result(parsed: dict[str, Any]) -> dict[str, Any]:
    text = collect_openai_text(parsed)
    stripped = text.strip()
    had_code_fence = stripped.startswith("```") or "```json" in stripped
    valid_json = False
    try:
        json.loads(stripped)
        valid_json = True
    except Exception:
        valid_json = False
    return {
        "valid_json": valid_json,
        "had_code_fence": had_code_fence,
        "raw_response_length": len(text),
        "sample_output": text,
    }


def extract_openai_tool_use_result(parsed: dict[str, Any]) -> dict[str, Any]:
    tool_called = None
    arguments_valid_json = False
    city_arg = None
    raw_arguments: Any = None
    choices = parsed.get("choices", [])
    if choices and isinstance(choices[0], dict):
        message = choices[0].get("message", {})
        tool_calls = message.get("tool_calls", [])
        if tool_calls and isinstance(tool_calls[0], dict):
            tool_call = tool_calls[0]
            function = tool_call.get("function", {})
            tool_called = function.get("name")
            raw_arguments = function.get("arguments")
            if isinstance(raw_arguments, str):
                try:
                    arguments = json.loads(raw_arguments)
                except Exception:
                    arguments_valid_json = False
                else:
                    arguments_valid_json = True
                    city_value = arguments.get("city")
                    if isinstance(city_value, str):
                        city_arg = city_value
    return {
        "tool_called": tool_called,
        "arguments_valid_json": arguments_valid_json,
        "city_arg": city_arg,
        "raw_arguments": raw_arguments,
    }


def collect_openai_text(parsed: dict[str, Any]) -> str:
    choices = parsed.get("choices", [])
    if not choices or not isinstance(choices[0], dict):
        return ""
    message = choices[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


def extract_error_message(payload: Any) -> str:
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str):
                return message
        detail = payload.get("detail")
        if isinstance(detail, str):
            return detail
        message = payload.get("message")
        if isinstance(message, str):
            return message
    return str(payload)


def average_latency_ms(result: dict[str, Any]) -> int | None:
    latencies = [
        case.get("latency_ms")
        for case in (
            result["connectivity"],
            result["structured_output"],
            result["tool_use"],
        )
        if case.get("ok") and isinstance(case.get("latency_ms"), int)
    ]
    if not latencies:
        return None
    return int(sum(latencies) / len(latencies))


def summarize_findings(
    results: list[dict[str, Any]],
    endpoints: dict[str, dict[str, Any]],
) -> list[str]:
    findings: list[str] = []
    for provider_key, endpoint in endpoints.items():
        if not endpoint["configured"]:
            label = "Anthropic-native" if provider_key == "anthropic" else "OpenAI-compatible"
            findings.append(f"{label} endpoint was not configured, so no probe calls were made.")
    for result in results:
        provider = result["provider"]
        model = result["model"]
        if result["connectivity"]["ok"]:
            findings.append(
                f"{provider}/{model} responded to the basic chat probe in "
                f"{result['connectivity']['latency_ms']} ms."
            )
        else:
            findings.append(
                f"{provider}/{model} failed connectivity: "
                f"{result['connectivity'].get('error', 'unknown error')}."
            )
            continue
        if result["structured_output"]["ok"] and result["structured_output"]["valid_json"]:
            findings.append(
                f"{provider}/{model} returned valid JSON in the structured-output probe."
            )
        elif result["structured_output"]["ok"]:
            findings.append(
                f"{provider}/{model} answered the structured-output probe "
                "but did not return valid JSON."
            )
        else:
            findings.append(
                f"{provider}/{model} failed the structured-output probe: "
                f"{result['structured_output'].get('error', 'unknown error')}."
            )
        if result["tool_use"]["ok"] and result["tool_use"]["tool_called"]:
            city_arg = result["tool_use"].get("city_arg")
            city_display = (
                json.dumps(city_arg, ensure_ascii=True) if city_arg is not None else "null"
            )
            findings.append(
                f"{provider}/{model} emitted tool-use for `{result['tool_use']['tool_called']}` "
                f"with city={city_display}."
            )
        elif result["tool_use"]["ok"]:
            findings.append(f"{provider}/{model} returned HTTP 200 but did not emit a tool call.")
        else:
            findings.append(
                f"{provider}/{model} failed the tool-use probe: "
                f"{result['tool_use'].get('error', 'unknown error')}."
            )
    return findings[:5]


def architecture_recommendation(results: list[dict[str, Any]]) -> str:
    successful_tool_use = [
        result
        for result in results
        if result["tool_use"]["ok"]
        and bool(result["tool_use"].get("tool_called"))
        and bool(result["tool_use"].get("arguments_valid_json"))
    ]
    openai_success = [result for result in successful_tool_use if result["provider"] == "openai"]
    anthropic_success = [
        result for result in successful_tool_use if result["provider"] == "anthropic"
    ]

    if openai_success:
        best = openai_success[0]
        city_arg = best["tool_use"].get("city_arg")
        city_display = json.dumps(city_arg, ensure_ascii=True) if city_arg is not None else "null"
        return (
            "The most practical T4-B path is OpenAI-compatible function calling. "
            f"{best['model']} reached HTTP 200 for all three probe cases, returned valid JSON, "
            f"and emitted a stable `get_weather` tool call with city={city_display}. "
            "That is enough evidence to build the first agentic loop on top of the OpenAI-style "
            "tool-calling contract."
        )
    if anthropic_success:
        best = anthropic_success[0]
        return (
            "The most practical T4-B path is Claude native tool-use. "
            f"{best['model']} completed the Anthropic-native probe with working tool-use, "
            "so the next iteration can safely target `messages.create(..., tools=[...])`."
        )

    chat_only = [
        result
        for result in results
        if result["connectivity"]["ok"] and not result["tool_use"].get("tool_called")
    ]
    if chat_only:
        model_list = ", ".join(f"{item['provider']}/{item['model']}" for item in chat_only[:3])
        return (
            "The current probe only supports a chat-first fallback path. "
            f"For example, {model_list} completed basic chat but did not expose stable tool-use. "
            "T4-B is better off starting with a manual tool loop or ReAct-style JSON actions "
            "before attempting a true multi-turn tool agent."
        )

    return (
        "这次 probe 没有拿到任何可用的 tool-use 证据，甚至基础连通性也不足。"
        "在这种情况下不建议直接推进真 agentic loop；先把 provider / proxy 能力矩阵跑通会更稳。"
    )


def build_markdown_report(
    probed_at: str,
    endpoints: dict[str, dict[str, Any]],
    results: list[dict[str, Any]],
) -> str:
    lines: list[str] = []
    lines.append("# T4 Probe Report: LLM Provider Capability Matrix")
    lines.append("")
    lines.append(f"Probe date: {date.fromisoformat(probed_at[:10]).isoformat()}")
    lines.append("")
    lines.append("## Endpoints tested")
    lines.append("")
    lines.append("| Endpoint | Configured | Base URL |")
    lines.append("|---|---|---|")
    lines.append(
        f"| Anthropic-native | {'yes' if endpoints['anthropic']['configured'] else 'no'} | "
        f"{endpoints['anthropic']['base_url']} |"
    )
    lines.append(
        f"| OpenAI-compatible | {'yes' if endpoints['openai']['configured'] else 'no'} | "
        f"{endpoints['openai']['base_url']} |"
    )
    lines.append("")
    lines.append("## Capability matrix")
    lines.append("")
    lines.append(
        "| Provider | Model | Connectivity | Structured JSON | Tool-Use | Latency (avg ms) |"
    )
    lines.append("|---|---|:-:|:-:|:-:|---:|")
    if results:
        for result in results:
            latency = average_latency_ms(result)
            connectivity = "yes" if result["connectivity"]["ok"] else "no"
            structured = (
                "yes"
                if result["structured_output"]["ok"] and result["structured_output"]["valid_json"]
                else ("no" if result["structured_output"]["ok"] else "-")
            )
            tool_use = (
                "yes"
                if result["tool_use"]["ok"] and result["tool_use"].get("tool_called")
                else ("no" if result["tool_use"]["ok"] else "-")
            )
            lines.append(
                f"| {result['provider']} | {result['model']} | "
                f"{connectivity} | "
                f"{structured} | "
                f"{tool_use} | "
                f"{latency if latency is not None else '-'} |"
            )
    else:
        lines.append("| - | - | - | - | - | - |")
    lines.append("")
    lines.append("## Key findings")
    lines.append("")
    for finding in summarize_findings(results, endpoints):
        lines.append(f"- {finding}")
    if not results:
        lines.append("- No endpoints were configured, so the probe produced an empty matrix.")
    lines.append("")
    lines.append("## Architecture recommendation")
    lines.append("")
    lines.append(architecture_recommendation(results))
    lines.append("")
    lines.append("## Raw data")
    lines.append("")
    lines.append("See `data/probe/llm_capability_matrix.json` for per-request raw outputs.")
    lines.append("")
    return "\n".join(lines)


async def run_probe() -> dict[str, Any]:
    settings = ProbeSettings()
    anthropic_endpoint = EndpointConfig(
        provider="anthropic",
        base_url=settings.probe_anthropic_base_url,
        api_key=settings.probe_anthropic_api_key,
    )
    openai_endpoint = EndpointConfig(
        provider="openai",
        base_url=settings.probe_openai_base_url,
        api_key=settings.probe_openai_api_key,
    )

    endpoints = {
        "anthropic": {
            "base_url": anthropic_endpoint.display_base_url(),
            "configured": anthropic_endpoint.configured,
        },
        "openai": {
            "base_url": openai_endpoint.display_base_url(),
            "configured": openai_endpoint.configured,
        },
    }

    results: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        if anthropic_endpoint.configured:
            for model in ANTHROPIC_MODELS_TO_PROBE:
                results.append(await probe_anthropic_model(client, anthropic_endpoint, model))
        if openai_endpoint.configured:
            for model in OPENAI_MODELS_TO_PROBE:
                results.append(await probe_openai_model(client, openai_endpoint, model))

    return {
        "probed_at": datetime.now(UTC).isoformat(),
        "endpoints": endpoints,
        "results": results,
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report = asyncio.run(run_probe())
    JSON_REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown = build_markdown_report(report["probed_at"], report["endpoints"], report["results"])
    MARKDOWN_REPORT_PATH.write_text(markdown + "\n", encoding="utf-8")

    if not any(endpoint["configured"] for endpoint in report["endpoints"].values()):
        print(
            "No probe endpoints configured. Set PROBE_ANTHROPIC_* or PROBE_OPENAI_* environment "
            "variables and rerun the script."
        )
    print(f"Wrote JSON report to {JSON_REPORT_PATH}")
    print(f"Wrote Markdown report to {MARKDOWN_REPORT_PATH}")
    print(markdown)


if __name__ == "__main__":
    main()
