# T4-B Before/After: Legacy Pipeline vs Agentic Loop

## Summary (mock mode, reproducible)

| Metric | Legacy | Agentic | Delta |
|---|---:|---:|---:|
| Deals submitted | 2 | 4 | +2 |
| Deals accepted (post evidence validation) | 2 | 3 | +1 |
| Unique destinations discovered | 2 | 3 | +1 |
| Destinations outside legacy whitelist | 0 | 1 | +1 |
| Tool calls per run | 18 | 8 | -10 |
| Run duration (mock ms) | 1 | 24 | +23 |

## Agentic evidence rejection detail

Of the 4 deals submitted by the agent, 3 passed evidence validation and 1 was rejected (`evidence_not_in_source`). This is the T3 validator working as designed: even though the agent has more freedom in deciding what to submit, the same evidence-grounding rule applies to its output. Legacy mode's evidence validation happens earlier in the pipeline (inside `price_parser`), so its rejection counts are not directly comparable here.

## Design rationale

1. We keep legacy mode because it is still the cheapest and most predictable path for scheduled batch runs, cron jobs, and CI smoke checks. Agentic mode is powerful, but not every job should spend tool budget and latency on open-ended exploration.
2. Agentic mode does something legacy cannot: it chooses its own next query and decides when to stop. In this mock benchmark it surfaces `西安`, which sits outside the hardcoded legacy shortlist for this run, and it also adds `重庆`, which legacy did not find.
3. The tradeoff is cost and complexity. Agentic mode uses more tool calls, more iterations, and more accumulated context. That is acceptable for interactive exploration, but it should not replace legacy as the default deterministic path.

## When to use which

- 定时批量任务 -> legacy (cheap, stable, predictable)
- 用户主动查询 -> agentic (broader coverage, adaptive search strategy)
- 新 origin_city 的初次探索 -> agentic (can adjust queries on the fly)
- CI/CD 冒烟测试 -> legacy (must stay reproducible)

## Known limitations

- The mock benchmark is scripted and deterministic. It proves control flow and validation behavior, not real-model variance.
- A real agentic run can still hit iteration or tool-call ceilings before it finds enough diversity.
- Because `EvidenceValidator` falls back to exact-string matching for unknown destinations, agentic mode can admit an evidence-grounded city outside the alias table today. That is a real current constraint, not something we should hand-wave away.
- Real API runs will cost more than the mock numbers here suggest, which is one more reason legacy remains the default.
- Legacy and agentic modes route deals through different paths to reach T3 evidence validation. Legacy validates inside `price_parser`; agentic validates in the loop finalizer. The end guarantee is the same (every accepted Deal passed evidence validation), but per-mode rejection stats are not directly comparable without normalizing the pipeline path.

## Two lines of defense, still intact

- T2 (structured output): agentic `submit_deal` still goes through a strict tool schema, so arguments stay valid JSON.
- T3 (evidence validation): every submitted agentic deal is still validated against accumulated search/fetch context before it becomes a `Deal`.
