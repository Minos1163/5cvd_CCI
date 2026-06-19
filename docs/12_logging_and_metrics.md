# Logging And Metrics

Version: V1.0

---

# 1. 目标

日志系统必须回答：

发生了什么

为什么发生

什么时候发生

---

# 2. 日志原则

日志用于：

调试

复盘

审计

监控

禁止：

print调试

---

# 3. 日志等级

DEBUG

INFO

WARNING

ERROR

CRITICAL

---

# 4. DEBUG

仅开发使用

记录：

指标细节

状态变化

信号计算

---

# 5. INFO

记录：

开仓

平仓

加仓

减仓

状态切换

---

# 6. WARNING

记录：

异常波动

数据缺失

订单延迟

---

# 7. ERROR

记录：

下单失败

接口异常

持仓同步失败

---

# 8. CRITICAL

记录：

风控失效

账户异常

连续重大错误

---

# 9. 日志格式

统一JSON

示例：

{
  "ts":"2026-01-01",
  "level":"INFO",
  "module":"entry_engine",
  "event":"LONG_OPEN"
}

---

# 10. 日志目录

logs/

strategy/

execution/

risk/

system/

---

# 11. 状态机日志

必须记录：

from_state

to_state

reason

symbol

price

---

# 12. 开仓日志

必须记录：

symbol

side

entry_price

size

risk

---

# 13. 平仓日志

必须记录：

exit_reason

pnl

holding_time

---

# 14. 风控日志

记录：

stop move

tp hit

cooldown start

cooldown end

---

# 15. 执行日志

记录：

request

response

latency

order_id

---

# 16. 指标日志

DEBUG级别：

MACD

CCI

RSI

CVD

BOLL

---

# 17. 指标监控

统计：

信号数量

触发数量

成交数量

---

# 18. KPI

每日统计：

交易次数

胜率

净利润

亏损次数

---

# 19. 核心指标

Profit Factor

Sharpe

Max Drawdown

Expectancy

---

# 20. 状态机指标

统计：

FLAT时间

WATCH时间

PROBE时间

DIRECT时间

---

# 21. 风控指标

统计：

止损次数

止盈次数

强平次数

冷却次数

---

# 22. 系统指标

CPU

RAM

API延迟

订单延迟

---

# 23. Prometheus

建议输出：

/metrics

供Grafana读取

---

# 24. 每日报告

自动生成：

daily_report.html

---

# 25. 周报

自动生成：

weekly_report.html

---

# 26. 月报

自动生成：

monthly_report.html

---

# 27. 结论

没有日志

就没有策略

没有指标

就没有优化