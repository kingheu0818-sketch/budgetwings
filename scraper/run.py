from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from scraper.pipeline import normalize_deals
from scraper.registry import build_default_registry


async def run_scrapers(output_dir: Path = Path("data/deals")) -> Path:
    registry = build_default_registry()
    deals = normalize_deals(await registry.scrape_all())

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{datetime.now(UTC).date().isoformat()}.json"
    output_path.write_text(
        json.dumps(
            [deal.model_dump(mode="json") for deal in deals],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Collected {len(deals)} deals -> {output_path}")
    return output_path


def main() -> None:
    asyncio.run(run_scrapers())


if __name__ == "__main__":
    main()
