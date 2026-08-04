# AI300 Strategy Review Template

> **强制开篇: 上轮建议实施回顾(2026-08-04 追踪协议)**
> 先运行 `python scripts/recommendation_tracker.py check`; 存在未解决 P0 时必须逐条说明阻塞原因, 不得直接分析新窗口数据。
> 表格内容见 `docs/recommendations_tracking.md`(与追踪表保持一致):

| 建议ID | 优先级 | 内容摘要 | 实施状态 | 验证结果 |
|---|---|---|---|---|
| (从 recommendations_tracking.md 复制) |  |  |  |  |

Review window:

- Start:
- End:
- Config tier: conservative / balanced / aggressive
- Model version:

## KPI vs Target

| Metric | Conservative Target | Observed | Notes |
| --- | ---: | ---: | --- |
| Monthly return proxy | 15%-25% |  | Dry-run estimate only |
| Win rate | >70% |  | Signal-level until live fills exist |
| Trade count | 60-90 |  | 90-120 is aggressive target |
| Max drawdown | <15% |  | Dry-run proxy |
| Profit factor | >1.5 |  | Needs exit lifecycle |

## Gate Rejections

Top 3 rejection reasons:

1.
2.
3.

## Abnormal Decisions

List high-score decisions that later looked wrong:

- Timestamp:
- Symbol:
- Score:
- Reason:
- What happened:

## Stress Risk

- Largest estimated stress loss:
- Symbols contributing most:
- Any `BLOCK` stress decisions:

## Parameter Changes

| Parameter | Old | New | Reason | Approved By |
| --- | ---: | ---: | --- | --- |

## Next Risk Budget

- Keep tier:
- Promote tier:
- Reduce tier:
- Required follow-up:
