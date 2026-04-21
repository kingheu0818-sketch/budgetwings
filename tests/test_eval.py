from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import cast

from pydantic import HttpUrl

from eval.compare import compare_reports, render_comparison_markdown
from eval.dataset import GoldenDeal
from eval.metrics import calculate_metrics
from models.deal import Deal, TransportMode


def test_calculate_metrics_handles_price_match_and_quality_signals() -> None:
    golden = [
        GoldenDeal(
            origin_city="深圳",
            destination_city="清迈",
            price_range_min=500,
            price_range_max=1000,
            transport_mode=TransportMode.FLIGHT,
            is_international=True,
        ),
        GoldenDeal(
            origin_city="深圳",
            destination_city="曼谷",
            price_range_min=400,
            price_range_max=1200,
            transport_mode=TransportMode.FLIGHT,
            is_international=True,
        ),
    ]
    deals = [
        make_deal(
            destination_city="清迈",
            price_cny_fen=68000,
            booking_url="https://example.com/cnx",
            departure_date=date.today() + timedelta(days=10),
        ),
        make_deal(
            destination_city="首尔",
            price_cny_fen=50000,
            booking_url="https://example.com/sel",
            departure_date=date.today() - timedelta(days=1),
        ),
    ]

    metrics = calculate_metrics(golden, deals)

    assert metrics.price_accuracy == 1.0
    assert metrics.destination_recall == 0.5
    assert metrics.destination_precision == 0.5
    assert metrics.url_validity == 1.0
    assert metrics.data_freshness == 0.5
    assert metrics.diversity_score == 1.0
    assert metrics.matched_price_count == 1


def test_compare_reports_marks_improvements_and_regressions() -> None:
    report1 = {
        "metadata": {"generated_at": "2026-04-20T00:00:00Z"},
        "metrics": {
            "price_accuracy": 0.5,
            "destination_recall": 0.4,
            "destination_precision": 0.6,
            "url_validity": 0.8,
            "data_freshness": 1.0,
            "diversity_score": 0.5,
        },
    }
    report2 = {
        "metadata": {"generated_at": "2026-04-21T00:00:00Z"},
        "metrics": {
            "price_accuracy": 0.7,
            "destination_recall": 0.5,
            "destination_precision": 0.4,
            "url_validity": 1.0,
            "data_freshness": 1.0,
            "diversity_score": 0.6,
        },
    }

    diff = compare_reports(report1, report2)
    markdown = render_comparison_markdown(diff)

    assert "price_accuracy" in diff["improved"]
    assert "destination_precision" in diff["regressed"]
    assert "data_freshness" in diff["unchanged"]
    assert "Evaluation Comparison" in markdown
    assert "price_accuracy" in markdown


def make_deal(
    destination_city: str,
    price_cny_fen: int,
    booking_url: str,
    departure_date: date,
) -> Deal:
    return Deal(
        source="test",
        origin_city="深圳",
        destination_city=destination_city,
        price_cny_fen=price_cny_fen,
        transport_mode=TransportMode.FLIGHT,
        departure_date=departure_date,
        booking_url=cast(HttpUrl, booking_url),
        source_url=cast(HttpUrl, booking_url),
        scraped_at=datetime.now(UTC),
    )
