# Contributing

## How to propose a change

- Open an issue first for architectural changes or new dependencies.
- Keep pull requests scoped to one main idea.
- Major feature changes should ship with a benchmark before/after report.

## What you can add

- New LLM adapter by extending `llm/base.py::LLMAdapter`
- New tool by extending `tools/base.py::BaseTool`
- New destination aliases in `tools/destinations.py`
- New prompt templates under `prompts/`
- New evaluation metrics in `eval/metrics.py`
- New benchmark scripts under `scripts/bench_*.py`

## Quality bar

```bash
ruff check .
mypy .
pytest
```

## Benchmark convention

- Major changes belong with a benchmark report in `data/bench/`
- Benchmark scripts live in `scripts/bench_*.py`
- Prefer mock mode for reproducibility unless real API behavior is the point
- Keep metric names stable so before/after reports stay comparable

## Do not

- Edit `archive/` except to add new archive notices
- Add dependencies without discussion
- Skip the benchmark for changes that alter deal quality or agent behavior
- Commit secrets, tokens, cookies, or personal data
