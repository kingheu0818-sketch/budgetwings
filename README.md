# BudgetWings

> An LLM-powered travel deal agent with three layers of defense against model
> unreliability.

BudgetWings finds cheap travel deals via a web-searching AI agent, then turns
them into ranked recommendations and short guides. The interesting part is not
just that it works, but that each reliability upgrade ships with a quantified
before/after benchmark instead of a hand-wavy claim.

## Why this project

LLMs are great at generating plausible text. They are not great at being honest
about numbers, URLs, or destinations. Building a real product on top of them
requires **multiple independent layers of defense**: schema enforcement,
evidence grounding, and human-selectable fallback strategies, each validated
with benchmarks.

This project documents that process end-to-end:

| Layer | Problem | Result |
|---|---|---|
| [Structured Output (T2)](data/bench/T2_before_after.md) | LLM returns malformed JSON under noisy output formats | Parse success 46.7% -> **100%** |
| [Evidence Validation (T3)](data/bench/T3_before_after.md) | LLM invents prices and destinations even in clean JSON | Hallucination rejection **80%**, false positives **0%** |
| [Agentic Loop (T4-B)](data/bench/T4B_legacy_vs_agentic.md) | Hardcoded Scout pipeline cannot adapt its search path | Agentic finds **+1 destination** with **-55%** tool calls in mock bench |

**Full walkthrough: [`CASE_STUDY.md`](CASE_STUDY.md)**

## Architecture

```text
User / Cron
    |
    v
Scout -> EvidenceValidator -> Analyst -> Guide
    |            |                |         |
    v            v                v         v
web_search   grounded Deal    ranked Deal  Markdown guide
web_fetch    validation       selection    output
price_parser
```

The long-form architecture and roadmap live in [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Project Structure

- `CASE_STUDY.md`: portfolio-style walkthrough of T2, T3, and T4-B
- `agents/`: Scout, Analyst, Guide, Orchestrator, and LangGraph pipeline
- `archive/`: historical v1 docs and legacy crawler code kept for reference
- `data/bench/`: benchmark JSON and before/after reports
- `llm/`: provider-neutral LLM adapters for Claude and OpenAI
- `tools/`: web search, fetch, price parsing, weather, currency, visa, holiday
- `models/`: stable Pydantic data contracts
- `db/`: SQLite persistence and analytics
- `rag/`: local knowledge base for guide generation
- `docs/DECISIONS.md`: architecture decision records for major trade-offs
- `scripts/`: benchmark harnesses and maintenance scripts
- `mcp_server/`: MCP server entry for Claude Desktop and other clients

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

- `data/deals/YYYY-MM-DD_<mode>_<HHMMSS>.json`
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

- Workflow: [deploy.yml](.github/workflows/deploy.yml)
- Daily data refresh: [daily_run.yml](.github/workflows/daily_run.yml)

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
