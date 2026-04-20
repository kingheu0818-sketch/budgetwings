# Data Sources

BudgetWings starts with API-first data collection and keeps scraping polite by default.

## Priority

1. Official airline or public comparison APIs.
2. Rail and bus APIs with documented access rules.
3. Community-submitted deals through GitHub issues or pull requests.
4. HTML scraping only when allowed by the source's Terms of Service and robots policy.

## Environment variables

API keys are read from environment variables only. Current placeholders:

- `KIWI_API_KEY`
- `SKYSCANNER_API_KEY`
- `WEATHER_API_KEY`
- `EXCHANGE_RATE_API_KEY`
- `TELEGRAM_BOT_TOKEN`

## Deal normalization

Every source should output `models.Deal` with:

- price stored as integer CNY fen
- timezone-aware UTC `scraped_at`
- source name and booking URL
- transport mode normalized to `flight`, `train`, `bus`, or `carpool`
