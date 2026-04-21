from __future__ import annotations

from datetime import date, timedelta

from tools.destinations import DESTINATION_ALIASES
from tools.evidence_validator import EvidenceValidator, RejectionReason
from tools.price_parser import ExtractedDeal


def build_extracted(
    *,
    destination_city: str = "曼谷",
    price_cny: int = 388,
    evidence_text: str | None = "深圳飞曼谷 CNY 388",
) -> ExtractedDeal:
    return ExtractedDeal.model_validate(
        {
            "origin_city": "深圳",
            "destination_city": destination_city,
            "price_cny": price_cny,
            "transport_mode": "flight",
            "departure_date": (date.today() + timedelta(days=30)).isoformat(),
            "booking_url": "https://example.com/book",
            "source_url": "https://example.com/source",
            "evidence_text": evidence_text,
        }
    )


def validator() -> EvidenceValidator:
    return EvidenceValidator(DESTINATION_ALIASES)


def test_normalize_handles_full_width_and_whitespace() -> None:
    normalized = EvidenceValidator._normalize("  ＣＮＹ　３８８ \n 深圳飞曼谷\t")

    assert normalized == "cny 388 深圳飞曼谷"


def test_validate_rejects_missing_evidence() -> None:
    result = validator().validate(build_extracted(evidence_text=""), "深圳飞曼谷 CNY 388")

    assert result.is_valid is False
    assert result.reasons == (RejectionReason.MISSING_EVIDENCE,)


def test_validate_rejects_when_evidence_not_in_source() -> None:
    result = validator().validate(
        build_extracted(evidence_text="深圳飞曼谷 CNY 388"),
        "深圳飞清迈 CNY 388",
    )

    assert result.is_valid is False
    assert RejectionReason.EVIDENCE_NOT_IN_SOURCE in result.reasons


def test_validate_rejects_when_price_not_in_evidence() -> None:
    result = validator().validate(
        build_extracted(price_cny=388, evidence_text="深圳飞曼谷 CNY 1200"),
        "深圳飞曼谷 CNY 1200",
    )

    assert result.is_valid is False
    assert RejectionReason.PRICE_NOT_IN_EVIDENCE in result.reasons


def test_validate_accepts_plain_price_format() -> None:
    result = validator().validate(build_extracted(evidence_text="深圳飞曼谷 388"), "深圳飞曼谷 388")

    assert result.is_valid is True


def test_validate_accepts_cny_price_format() -> None:
    result = validator().validate(
        build_extracted(evidence_text="深圳飞曼谷 CNY 388"),
        "深圳飞曼谷 CNY 388",
    )

    assert result.is_valid is True


def test_validate_accepts_yen_symbol_price_format() -> None:
    result = validator().validate(
        build_extracted(evidence_text="深圳飞曼谷 ¥388"),
        "深圳飞曼谷 ¥388",
    )

    assert result.is_valid is True


def test_validate_accepts_yuan_suffix_price_format() -> None:
    result = validator().validate(
        build_extracted(evidence_text="深圳飞曼谷 388元"),
        "深圳飞曼谷 388元",
    )

    assert result.is_valid is True


def test_validate_accepts_zero_decimal_price_format() -> None:
    result = validator().validate(
        build_extracted(evidence_text="深圳飞曼谷 RMB 388.00"),
        "深圳飞曼谷 RMB 388.00",
    )

    assert result.is_valid is True


def test_validate_does_not_match_price_inside_larger_number() -> None:
    result = validator().validate(
        build_extracted(price_cny=388, evidence_text="深圳飞曼谷 1388元"),
        "深圳飞曼谷 1388元",
    )

    assert result.is_valid is False
    assert RejectionReason.PRICE_NOT_IN_EVIDENCE in result.reasons


def test_validate_rejects_when_destination_missing_from_evidence() -> None:
    result = validator().validate(
        build_extracted(destination_city="清迈", evidence_text="深圳飞曼谷 CNY 388"),
        "深圳飞曼谷 CNY 388",
    )

    assert result.is_valid is False
    assert RejectionReason.DESTINATION_NOT_IN_EVIDENCE in result.reasons


def test_validate_accepts_destination_alias_match() -> None:
    result = validator().validate(
        build_extracted(destination_city="曼谷", evidence_text="Shenzhen to Bangkok CNY 388"),
        "Shenzhen to Bangkok CNY 388",
    )

    assert result.is_valid is True


def test_validate_returns_multiple_reasons() -> None:
    result = validator().validate(
        build_extracted(
            destination_city="清迈",
            price_cny=388,
            evidence_text="深圳飞曼谷 CNY 1200",
        ),
        "深圳飞曼谷 CNY 1200",
    )

    assert result.is_valid is False
    assert set(result.reasons) == {
        RejectionReason.PRICE_NOT_IN_EVIDENCE,
        RejectionReason.DESTINATION_NOT_IN_EVIDENCE,
    }


def test_validate_accepts_fully_valid_sample() -> None:
    result = validator().validate(
        build_extracted(
            destination_city="曼谷",
            price_cny=388,
            evidence_text="深圳飞曼谷 CNY 388，5月20日出发",
        ),
        "活动页写着：深圳飞曼谷 CNY 388，5月20日出发，数量有限。",
    )

    assert result.is_valid is True
    assert result.reasons == ()
