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

- 结构化输出消除了“正则只抓到第一个代码块”的脆弱路径。`noisy_multi_block_tokyo` 在 baseline 中因为第一个 ```json``` 代码块只是摘要对象而失败；structured 版本直接走 schema tool-use，成功提取出 1 条 deal。
- 结构化输出也消除了“模型先解释、再给 JSON”导致的 `json.loads` 失败。`noisy_prefixed_commentary_osaka` 和 `recorded_2` 在 baseline 中都因为 JSON 前有解释文字而报错；structured 版本直接返回 schema 匹配对象，成功恢复。
- 对“没有明确价格”或“明显是陷阱样本”的处理从“报错”变成了“成功返回空列表”。这让 pipeline 更容易做后续统计和降级，而不是把这类样本混成解析异常。

## Known limitations

- 幻觉问题还没有完全解决。本次只增加了 `evidence_text` 字段和相关埋点，**证据完整性校验** 仍然留给 T3。
- benchmark 目前跑的是 mock LLM，用来稳定复现失败模式并做 before/after 对比；真实线上效果仍然需要结合 live provider 继续观察。
- `ExtractedDeal` 是给 LLM 用的中间 schema，不等于最终业务契约。真正的业务约束仍然以 `models/deal.py` 和后续 validator 为准。
