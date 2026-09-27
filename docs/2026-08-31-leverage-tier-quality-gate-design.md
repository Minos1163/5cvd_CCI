# 4x 杠杆质量门控设计(评审 5.2 节)— shadow 先行

**日期:** 2026-08-31
**依据:** 08-31 评审 5.2 节 + 三笔大额亏损归因(均 Q1 SHORT + 4x 无质量门)

---

## 1. 现状(代码事实)

`src/signals/entry_chain.py` `_select_leverage`(L614-635):

```python
if action not in {"PROBE", "DIRECT"}: return 0
if rolling_sharpe_20 < 0: return 2          # 唯一质量约束
if atr_pct > 0.03: return 3                  # 高波动降档
if atr_pct > 0.015: return 4 if DIRECT else 3
if score >= 90 and action == "DIRECT":       # 仅 90+ 检查 5x 质量门
    if not _fib_pa_5x_requirements_met(...): return 4
    return 5
return 4 if action == "DIRECT" else 3        # ← DIRECT 默认 4x,无组件门
```

**结论:5x 有严格质量门(fib≥13/pa≥9/cci≥9/rr≥4),4x 无任何组件门**——总分之上的 DIRECT 直接得 4x。

## 2. 设计:三档杠杆全部质量门控(评审 5.2 规格)

```python
LEVERAGE_TIER_QUALITY_GATES = {
    5: {"fib_min": 13.0, "pa_min": 9.0, "rr_min": 4.0, "cci_min": 7.0},   # 现状保留
    4: {"fib_min": 10.0, "pa_min": 7.0, "rr_min": 5.0},                   # 新增(rr 不低于 5x)
    3: {"fib_min": 6.0,  "pa_min": 6.0, "rr_min": 2.0},                   # 新增
    2: {},                                                                 # 默认保守档
}
```

**设计理由(rr 为何 4x 档要求 ≥5)**:三笔大额亏损 MFE 0.36-0.75R——RR 几何质量差是 4x 档被忽视的缺口;4x 在"未达 5x 质量"时承接,应至少不比 5x 的 rr 门槛更松。

## 3. shadow 反事实(先记录不强制)

`scripts/leverage_tier_gate_shadow.py`:读窗口 decisions,对 `action=DIRECT` 的决策应用 4x 门控,输出:
- 若门控生效,多少 DIRECT 决策会被降档(4x→3x/2x);
- 三笔大额亏损样本(BCH/DOGE 08-24、SOL 08-28)的 rr 组件是否达标 → 是否会降档;
- 按象限/方向拆分(验证 Q1 SHORT 是否集中。

**不直接改 live 杠杆**(数值需历史回测校准,评审 5.2;遵循 20 笔纪律)。

## 4. 与候选 1(行为确认)的关系

- 4x 门控(本节)解决"质量不足却给 4x";
- 行为确认(评审 5.1/候选1)解决"状态质量高但无突破行为确认";
- 两者可组合:最终杠杆 = min(质量门控档, 波动率档);行为确认先作为诊断字段记录(评审 5.1 扩展建议)。
