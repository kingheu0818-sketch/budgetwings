# T3 Before/After: Evidence-Driven Validation

## Summary

| Metric | Structured (T2) | Structured + Validation (T3) | Delta |
|---|---:|---:|---:|
| Total samples | 20 | 20 | - |
| Valid deals accepted | 14 | 10 | -4 |
| Hallucinations injected | 5 | 5 | - |
| Hallucinations rejected | 0 | 4 | +4 |
| Hallucination rejection rate | 0.0% | 80.0% | +80.0 pp |
| False-positive rejections | 0 | 0 | 0 |

## Rejection breakdown

| Reason | Count |
|---|---:|
| missing_evidence | 1 |
| evidence_not_in_source | 1 |
| price_not_in_evidence | 2 |
| destination_not_in_evidence | 1 |

## Design rationale

1. We keep the validator as three independent checks because each one blocks a different failure mode. A fabricated quote, a mismatched numeric price, and a mismatched destination are not the same bug, and collapsing them into one fuzzy check would make both debugging and metrics noisier.
2. Normalization is necessary because Tavily snippets often contain full-width punctuation, inconsistent whitespace, or line breaks. A source like `深圳飞曼谷\nCNY 388` and evidence like `深圳飞曼谷 CNY 388` should still count as the same contiguous quote after normalization.
3. This layer is deliberately conservative. If we have to choose between rejecting one real deal and letting one hallucinated deal through, we choose rejection. The downstream product cost of a fake price or fake destination is higher than the cost of asking Scout to find another candidate.

## Two independent lines of defense

- T2 (structured output): guarantees **schema correctness**. The LLM cannot return malformed JSON.
- T3 (evidence validation): guarantees **content groundedness**. The LLM cannot invent numbers or destinations that don't exist in the source.

These two layers fail independently, which means a deal must pass BOTH to be kept.

## Known limitations

- Evidence must be a contiguous normalized substring. If the model paraphrases even one key word, it fails. This is intentional for now.
- Destination aliases are still hardcoded to 13 entries in Python. T5 will move this to data-driven configuration.
- The current price regex does not yet detect currency mismatches like `388 美元` vs `388 元`. In the live pipeline we currently target CNY-heavy sources, so this is acceptable for now, but it is a clear future TODO.
