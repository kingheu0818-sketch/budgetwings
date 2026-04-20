# BudgetWings

BudgetWings is an open-source low-cost travel intelligence project. It collects cheap flight, rail, bus, and community-submitted travel deals, then turns those deals into short trip guides for two core personas: workers with tight weekend schedules and students with flexible time but lower budgets.

The MVP follows the product requirements in `PRD.md`: API-first data collection, Pydantic data models, YAML destination guide templates, persona-aware filtering, and GitHub Actions automation.

## What is included now

- Python 3.11+ project configuration in `pyproject.toml`
- Pydantic v2 models for deals, guide templates, and personas
- Async scraper base class with 30s timeout, 3 retries, user-agent, and simple rate limiting
- Environment-based configuration through `pydantic-settings`
- Initial repository structure from PRD 7.2
- Sample guide templates under `guides/`
- Pull request CI for `ruff`, `mypy`, and `pytest`

## Repository layout

```text
scraper/                  Data collection interfaces and source scrapers
engine/                   Ranking, guide generation, persona filtering, notification logic
models/                   Pydantic data contracts
guides/                   YAML destination guide templates
web/                      Future static web frontend
bot/                      Future Telegram bot
data/deals/               Generated deal JSON files
docs/                     Contributor and data-source documentation
.github/workflows/        CI, scrape, and deploy workflows
```

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
pytest
```

## Configuration

Copy `.env.example` to `.env` and fill only the keys you need. API keys must come from environment variables and should never be committed.

Common variables:

- `KIWI_API_KEY`
- `SKYSCANNER_API_KEY`
- `WEATHER_API_KEY`
- `EXCHANGE_RATE_API_KEY`
- `TELEGRAM_BOT_TOKEN`

## Development checks

```bash
ruff check .
mypy .
pytest
```

## Contributing

Read `docs/CONTRIBUTING.md` for contribution rules. Destination guides are plain YAML files, so non-code contributions are welcome too.
