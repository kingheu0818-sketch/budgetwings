# T4 Probe Report: LLM Provider Capability Matrix

Probe date: 2026-04-21

## Endpoints tested

| Endpoint | Configured | Base URL |
|---|---|---|
| Anthropic-native | no | not configured |
| OpenAI-compatible | yes | https://api.ikuncode.cc/v1 |

## Capability matrix

| Provider | Model | Connectivity | Structured JSON | Tool-Use | Latency (avg ms) |
|---|---|:-:|:-:|:-:|---:|
| openai | gpt-5.4 | yes | yes | yes | 1333 |
| openai | gpt-5.4-mini | yes | yes | yes | 1791 |
| openai | claude-sonnet-4-20250514 | no | - | - | - |

## Key findings

- Anthropic-native endpoint was not configured, so no probe calls were made.
- openai/gpt-5.4 responded to the basic chat probe in 1309 ms.
- openai/gpt-5.4 returned valid JSON in the structured-output probe.
- openai/gpt-5.4 emitted tool-use for `get_weather` with city="\u6df1\u5733".
- openai/gpt-5.4-mini responded to the basic chat probe in 1728 ms.

## Architecture recommendation

The most practical T4-B path is OpenAI-compatible function calling. gpt-5.4 reached HTTP 200 for all three probe cases, returned valid JSON, and emitted a stable `get_weather` tool call with city="\u6df1\u5733". That is enough evidence to build the first agentic loop on top of the OpenAI-style tool-calling contract.

## Raw data

See `data/probe/llm_capability_matrix.json` for per-request raw outputs.

