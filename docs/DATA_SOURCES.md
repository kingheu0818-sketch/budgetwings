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

## Kiwi.com Tequila API

Kiwi is the first MVP flight source. The scraper uses the Tequila `/v2/search`
endpoint with `fly_to=anywhere`, `flight_type=oneway`, `curr=CNY`, and
`price_to=1500`.

### Apply for access

1. Open the Kiwi/Travelpayouts affiliate access flow.
2. Create or select your project.
3. Connect the Kiwi.com affiliate program.
4. Request API access for the project.
5. Store the issued API key as `KIWI_API_KEY`.

Current public access requirements can change. The Travelpayouts Kiwi API help
page currently says API access is only available to projects with at least
50,000 monthly active users. Treat this as an external platform limit and verify
it before planning production usage.

### Environment variable

```bash
KIWI_API_KEY=your_tequila_api_key
```

The scraper sends this value in the `apikey` request header.

### Free tier and operational limits

- Access is gated by Kiwi/Travelpayouts program approval.
- Rate limits and quota depend on the approved account and program terms.
- Keep scheduled runs conservative; BudgetWings defaults to one request per
  second between source calls.
- Do not scrape booking pages. Use the API response and send users to Kiwi via
  the returned `deep_link`.

## Deal normalization

Every source should output `models.Deal` with:

- price stored as integer CNY fen
- timezone-aware UTC `scraped_at`
- source name and booking URL
- transport mode normalized to `flight`, `train`, `bus`, or `carpool`
