# Configuration Schema

Version: V1.0

---

# 1. 目标

统一所有配置。

禁止：

- 硬编码
- 魔法数字
- 多处重复定义

所有参数必须来自配置。

---

# 2. 配置结构

configs/

├── strategy.yaml
├── risk.yaml
├── execution.yaml
├── universe.yaml
├── logging.yaml
└── backtest.yaml

---

# 3. strategy.yaml

负责：

策略逻辑参数

示例：

strategy:

  name: macd_cci_cvd_v1

  enabled: true

  timeframes:

    trigger: 15m

    confirm: 30m

    trend: 1h

    context: 4h

---

# 4. 指标参数

indicators:

  macd:

    fast: 12

    slow: 26

    signal: 9

  cci:

    period: 20

  rsi:

    period: 14

  boll:

    period: 20

    std: 2

---

# 5. 入场参数

entry:

  cci_long: 100

  cci_short: -100

  rsi_reclaim: 50

  cvd_slope_window: 5

---

# 6. Probe配置

probe:

  enabled: true

  size_ratio: 0.25

  upgrade_r_multiple: 1.0

---

# 7. Direct配置

direct:

  enabled: true

  require_cvd_confirm: true

---

# 8. risk.yaml

risk:

  risk_per_trade_pct: 0.01

  daily_loss_limit_pct: 0.05

  weekly_loss_limit_pct: 0.12

  max_drawdown_pct: 0.20

---

# 9. 止损参数

stop:

  atr_period: 14

  atr_mult: 1.5

  min_stop_pct: 0.005

---

# 10. 止盈参数

take_profit:

  tp1_r: 1

  tp2_r: 2

  tp3_r: 4

---

# 11. execution.yaml

execution:

  exchange: binance

  leverage: 3

  use_market_order: true

---

# 12. 滑点

slippage:

  base_bps: 3

  high_vol_bps: 8

---

# 13. universe.yaml

universe:

  refresh_interval_hours: 24

  max_symbols: 20

---

# 14. logging.yaml

logging:

  level: INFO

  save_json: true

  save_csv: true

---

# 15. backtest.yaml

backtest:

  start: "2024-01-01"

  end: "2025-01-01"

  initial_capital: 10000

---

# 16. 配置读取原则

所有模块：

只读配置。

禁止修改配置。

---

# 17. 配置优先级

默认配置

↓

环境配置

↓

用户覆盖

---

# 18. 热更新

允许：

日志等级

允许：

监控参数

禁止：

策略核心参数

---

# 19. 配置版本

每个配置必须包含：

version

示例：

version: 1.0.0

---

# 20. 结论

配置决定行为。

代码不应该决定行为。