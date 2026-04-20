# BudgetWings

BudgetWings is an AI Agent project for low-cost travel intelligence. Instead of
depending on one flight API or brittle crawlers, it uses an orchestrated set of
LLM-powered agents and tools to search the web, extract cheap travel deals,
rank them for different personas, and generate short travel guides.

The v2 architecture is described in `ARCHITECTURE.md`.

## Agent Architecture

- `agents/`: Scout, Analyst, Guide, and Orchestrator.
- `llm/`: provider-neutral LLM adapters for Claude and OpenAI.
- `tools/`: web search, web fetch, price parsing, weather, currency, visa, and holiday tools.
- `models/`: stable Pydantic data contracts for deals, guides, and personas.
- `prompts/`: system prompt templates for the three core agents.
- `scraper/`: legacy crawler layer kept for compatibility.

## Quick Start

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

If dependency downloads are slow in mainland China, use the Tsinghua PyPI mirror:

```bash
python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -e ".[dev]"
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -e ".[dev]"
```

## Configuration

Copy `.env.example` to `.env` and set the provider you want to use.

Claude:

```env
BUDGETWINGS_LLM_PROVIDER=claude
BUDGETWINGS_LLM_MODEL=claude-sonnet-4-20250514
ANTHROPIC_API_KEY=your_key
TAVILY_API_KEY=your_key
```

OpenAI:

```env
BUDGETWINGS_LLM_PROVIDER=openai
BUDGETWINGS_LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=your_key
TAVILY_API_KEY=your_key
```

All API keys must come from environment variables. Do not commit `.env`.

## CLI

Run the full Scout -> Analyst -> Guide pipeline:

```bash
python cli.py run --city 深圳 --persona worker --top 10
```

Generate a guide for a previously stored deal:

```bash
python cli.py guide --deal-id DEAL_ID --persona student
```

Outputs are written to:

- `data/deals/YYYY-MM-DD.json`
- `data/guides/DEAL_ID.md`

## Telegram Bot

The bot reads local JSON files from `data/deals/` and never calls an LLM.

```bash
TELEGRAM_BOT_TOKEN=your_token python -m bot.main
```

Commands:

- `/start`
- `/mode worker`
- `/mode student`
- `/deals`
- `/deals 清迈`
- `/budget 2000`

## Static Website

The web app is a Next.js 14 static export. It reads `data/deals/*.json` and
`data/guides/*.md` at build time.

```bash
cd web
npm install
npm run dev
```

Build static files:

```bash
npm run build
```

## Development Checks

```bash
ruff check .
mypy .
pytest
```

## Contributing

Read `docs/CONTRIBUTING.md`. Contributions can add new tools, prompt templates,
LLM adapters, visa policies, or destination guide logic.
