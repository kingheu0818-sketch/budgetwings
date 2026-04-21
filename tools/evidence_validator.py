"""Evidence-driven anti-hallucination validator for extracted deals.

This module is the second line of defense after LLM structured output.
Structured output guarantees the shape of the response; evidence validation
guarantees that the content is grounded in the actual input text.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tools.price_parser import ExtractedDeal


class RejectionReason(StrEnum):
    MISSING_EVIDENCE = "missing_evidence"
    EVIDENCE_NOT_IN_SOURCE = "evidence_not_in_source"
    PRICE_NOT_IN_EVIDENCE = "price_not_in_evidence"
    DESTINATION_NOT_IN_EVIDENCE = "destination_not_in_evidence"


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    reasons: tuple[RejectionReason, ...]
    evidence_text: str


class EvidenceValidator:
    """Validate that an ExtractedDeal is grounded in the source text.

    Three independent checks (ALL must pass):
      1. Evidence substring check: evidence_text MUST be a contiguous
         (normalized) substring of the source_text. This blocks the LLM
         from fabricating or rewording quotes.
      2. Price consistency: the numeric price MUST appear in evidence_text.
         Allows common number formatting (',', ' ', '元', 'CNY').
      3. Destination consistency: the destination_city OR one of its aliases
         MUST appear in evidence_text.
    """

    def __init__(self, destination_aliases: dict[str, set[str]]) -> None:
        self._destination_aliases = {
            city: {self._normalize(alias) for alias in {city, *aliases} if self._normalize(alias)}
            for city, aliases in destination_aliases.items()
        }

    def validate(
        self,
        extracted: ExtractedDeal,
        source_text: str,
    ) -> ValidationResult:
        reasons: list[RejectionReason] = []
        normalized_source = self._normalize(source_text)
        normalized_evidence = self._normalize(extracted.evidence_text or "")

        if not normalized_evidence:
            reasons.append(RejectionReason.MISSING_EVIDENCE)
            return ValidationResult(
                is_valid=False,
                reasons=tuple(reasons),
                evidence_text=normalized_evidence,
            )

        if normalized_evidence not in normalized_source:
            reasons.append(RejectionReason.EVIDENCE_NOT_IN_SOURCE)

        if not self._price_in_evidence(extracted.price_cny, normalized_evidence):
            reasons.append(RejectionReason.PRICE_NOT_IN_EVIDENCE)

        if not self._destination_in_evidence(extracted.destination_city, normalized_evidence):
            reasons.append(RejectionReason.DESTINATION_NOT_IN_EVIDENCE)

        return ValidationResult(
            is_valid=not reasons,
            reasons=tuple(reasons),
            evidence_text=normalized_evidence,
        )

    @staticmethod
    def _normalize(text: str) -> str:
        normalized = unicodedata.normalize("NFKC", text)
        normalized = normalized.casefold()
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()

    def _price_in_evidence(self, price_cny: int, evidence_text: str) -> bool:
        escaped_price = re.escape(str(price_cny))
        pattern = re.compile(
            rf"(?<!\d)(?:[¥￥]|cny\s*|rmb\s*)?{escaped_price}(?:\.0+)?(?:\s*元)?(?!\d)"
        )
        return bool(pattern.search(evidence_text))

    def _destination_in_evidence(self, destination_city: str, evidence_text: str) -> bool:
        normalized_destination = self._normalize(destination_city)
        aliases = self._destination_aliases.get(normalized_destination, {normalized_destination})
        return any(alias and alias in evidence_text for alias in aliases)
