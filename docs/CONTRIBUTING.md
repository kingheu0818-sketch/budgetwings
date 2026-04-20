# Contributing to BudgetWings

BudgetWings welcomes code, data-source notes, and destination guide templates.

## Ways to contribute

- Add or improve guide YAML files under `guides/`.
- Add a new scraper under `scraper/sources/` by subclassing `BaseScraper`.
- Improve ranking, filtering, or guide generation in `engine/`.
- Report stale deals, broken booking links, or data-source risks in issues.

## Local checks

```bash
python -m pip install -e ".[dev]"
ruff check .
mypy .
pytest
```

If PyPI access is slow, install through the Tsinghua mirror:

```bash
python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -e ".[dev]"
```

## Safety rules

- Do not commit API keys, cookies, tokens, or personal data.
- Prefer official APIs and respect data-source Terms of Service.
- Keep prices in CNY fen and datetimes timezone-aware UTC in Python models.
- Mark the data source and scrape time for every deal.
