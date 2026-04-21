# BudgetWings

BudgetWings is an AI agent project for low-cost travel intelligence. Instead of
depending on one flight API or brittle crawlers, it uses an orchestrated set of
LLM-powered agents and tools to search the web, extract cheap travel deals,
rank them for different personas, and generate short travel guides.

The v2 architecture is described in `ARCHITECTURE.md`.

## Project Structure

- `agents/`: Scout, Analyst, Guide, Orchestrator, and LangGraph pipeline
- `llm/`: provider-neutral LLM adapters for Claude and OpenAI
- `tools/`: web search, fetch, price parsing, weather, currency, visa, holiday
- `models/`: stable Pydantic data contracts
- `db/`: SQLite persistence and analytics
- `rag/`: local knowledge base for guide generation
- `mcp_server/`: MCP server entry for Claude Desktop and other clients
- `scraper/`: legacy crawler layer kept for compatibility

## Quick Start

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

If you also want the MCP server entry for Claude Desktop, install the extra:

```bash
python -m pip install -e ".[dev,mcp]"
```

If downloads are slow in mainland China, use the Tsinghua mirror:

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
BUDGETWINGS_LLM_MODEL=gpt-5.4-mini
OPENAI_API_KEY=your_key
OPENAI_BASE_URL=https://your-proxy-or-compatible-endpoint/v1
TAVILY_API_KEY=your_key
```

All API keys must come from environment variables. Do not commit `.env`.

## CLI

Run the full Scout -> Analyst -> Guide pipeline:

```bash
python cli.py run --city 深圳 --persona worker --top 10 --engine graph
```

Generate a guide for a previously stored deal:

```bash
python cli.py guide --deal-id DEAL_ID --persona student
```

Run an evaluation against the golden dataset:

```bash
python cli.py eval --city 深圳 --persona worker --top 10 --save
python cli.py eval-compare --report1 eval/reports/2026-04-20.json --report2 eval/reports/2026-04-21.json
```

Outputs are written to:

- `data/deals/YYYY-MM-DD.json`
- `data/guides/DEAL_ID.md`
- `data/budgetwings.db`
- `eval/reports/YYYY-MM-DD.json`

## Telegram Bot

The bot reads local JSON files from `data/deals/` and does not call an LLM.

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

## MCP Server

BudgetWings can expose its tool layer as an MCP server for Claude Desktop and
other MCP clients.

Start the MCP server in stdio mode:

```bash
python -m mcp_server.server
```

Available MCP tools:

- `search_deals`: search and rank cheap deals for a city/persona
- `get_guide`: return guide Markdown by `deal_id` or destination
- `price_trend`: query historical price trend from SQLite
- `visa_check`: look up local visa policy data
- `weather_check`: query weather with Open-Meteo

Example Claude Desktop configuration is in `mcp_server/config.json`. Copy the
`budgetwings` entry into your local `claude_desktop_config.json`, then adjust
`command`, `cwd`, and environment variables for your machine.

## Static Website

The web app is a Next.js 14 static export. It reads `data/deals/*.json`,
`data/guides/*.md`, and `eval/reports/*.json` at build time.

```bash
cd web
npm install
npm run dev
```

Build static files:

```bash
npm run build
```

Pages included in the web app:

- `/` deals home with persona and price filters
- `/guide/[id]` guide detail page
- `/about` project overview
- `/eval` evaluation dashboard
- `/status` deployment/data health view

## Deployment

The repository is configured for static deployment on GitHub Pages.

- Workflow: [deploy.yml](D:/yu/project/budgetwings/.github/workflows/deploy.yml)
- Daily data refresh: [daily_run.yml](D:/yu/project/budgetwings/.github/workflows/daily_run.yml)

Deploy flow:

1. Push to `main`
2. GitHub Actions builds `web/`
3. Static files from `web/out/` are published to GitHub Pages
4. Daily pipeline updates `data/` and `eval/reports/`, which triggers a fresh site deployment

Expected Pages URL after the workflow succeeds:

- [https://kingheu0818-sketch.github.io/budgetwings/](https://kingheu0818-sketch.github.io/budgetwings/)

## Development Checks

```bash
ruff check .
mypy .
pytest
```

## Contributing

Read `docs/CONTRIBUTING.md`. Contributions can add new tools, prompt
templates, LLM adapters, visa policies, MCP tools, or destination guide logic.
