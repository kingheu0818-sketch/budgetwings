# T2 Before/After: price_parser Refactor

## Summary

| Metric | Baseline | Structured | Delta |
|---|---:|---:|---:|
| Total samples | 15 | 15 | - |
| Parse success rate | 46.7% | 100.0% | +53.3 pp |
| Total deals extracted | 7 | 9 | +2 |
| Pydantic validation failures | 0 | 0 | 0 |
| Empty result count | 0 | 6 | +6 |

## Notes

- Provider: mock
- Model: bench-mock
- Benchmark date: 2026-04-21
- Mock mode: true

## Key wins

- Structured output removes the "regex grabbed the wrong code block" failure mode.
  `noisy_multi_block_tokyo` failed in baseline because the first ```json``` block
  was only a summary object; the structured version recovered the actual deal.
- Structured output also removes the "model explains first, JSON later" failure mode.
  `noisy_prefixed_commentary_osaka` and `recorded_2` both failed in baseline
  because `json.loads` saw free text before JSON; the structured version no longer
  depends on that brittle parse step.
- Samples with no qualifying evidence now produce clean empty results instead of
  parse exceptions. That gives downstream pipeline code a much clearer signal.

## Failure mode analysis

The baseline shows `parse success rate = 46.7%` but `pydantic_validation_failures = 0`.
This is not a contradiction - it means every baseline failure happened at the
JSON parsing stage (regex extraction or `json.loads`), before any data reached
Pydantic. The structured-output refactor eliminates this entire class of
failures by construction: the LLM response is forced to satisfy the schema at
the SDK layer, so `json.loads` is never called on LLM free-text at all.

In other words, the refactor does not "improve" Pydantic acceptance; it
removes the fragile regex+parse layer that used to fail before Pydantic even
saw the data.

## Empty results as a product decision

`empty_result_count` goes from 0 -> 6. This is intentional, not a regression.
Samples with no explicit price (e.g. "last year's fare was about CNY 800" / trap samples) used to
raise parse errors in baseline; in structured output they correctly return
`success=True, deals=[]`. Downstream the pipeline can now distinguish
"parser failure" from "no qualifying deals", which enables cleaner retry
logic and cleaner metrics.

## Known limitations

- Hallucination risk is not fully solved yet. This refactor adds the
  `evidence_text` field and basic instrumentation, but evidence completeness
  and evidence-to-price validation are still T3 work.
- The benchmark currently runs in mock mode to reproduce failure patterns
  deterministically. Real-provider quality still needs continued observation.
- `ExtractedDeal` is an LLM-facing intermediate schema, not the final business
  contract. The authoritative downstream contract remains `models/deal.py`
  plus later validation layers.
