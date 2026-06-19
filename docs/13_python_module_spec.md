# Python Module Specification

Version: V1.0

---

# 1. 目标

定义项目最终模块结构。

禁止：

跨层调用

循环依赖

万能工具类

---

# 2. 项目结构

src/

config/

data/

indicators/

context/

signals/

state_machine/

risk/

execution/

portfolio/

backtest/

reporting/

utils/

---

# 3. data层

职责：

获取数据

缓存数据

标准化数据

禁止：

策略判断

---

# 4. indicators层

职责：

计算指标

输出结果

禁止：

生成交易信号

---

# 5. context层

职责：

多周期市场状态

输出：

BULL

BEAR

NEUTRAL

---

# 6. signals层

职责：

生成入场信号

输出：

LONG

SHORT

WAIT

---

# 7. state_machine层

职责：

状态管理

状态：

FLAT

WATCH

PROBE

DIRECT

MANAGE

EXIT

---

# 8. risk层

职责：

风险控制

仓位

止损

止盈

---

# 9. execution层

职责：

调用 binance_client

禁止：

策略逻辑

---

# 10. portfolio层

职责：

账户管理

组合风险

持仓同步

---

# 11. backtest层

职责：

回测

统计

绩效分析

---

# 12. reporting层

职责：

生成报告

HTML

CSV

Excel

---

# 13. utils层

职责：

公共工具

时间处理

文件处理

配置处理

---

# 14. 模块依赖

允许：

data

↓

indicators

↓

context

↓

signals

↓

state_machine

↓

risk

↓

execution

---

# 15. 禁止反向依赖

execution

不能调用

signal

risk

不能调用

backtest

---

# 16. BaseSignal

统一接口

class BaseSignal

generate()

---

# 17. BaseIndicator

统一接口

class BaseIndicator

calculate()

---

# 18. BaseRiskModel

统一接口

class BaseRiskModel

evaluate()

---

# 19. BaseExecution

统一接口

class BaseExecution

submit()

cancel()

sync()

---

# 20. Engine划分

market_engine

signal_engine

risk_engine

execution_engine

report_engine

---

# 21. StrategyContext

统一上下文对象

保存：

symbol

timeframe

indicators

state

risk

---

# 22. EventBus

统一事件

事件：

SIGNAL_CREATED

ORDER_FILLED

STOP_HIT

TP_HIT

---

# 23. DTO对象

统一数据传输

禁止：

dict乱飞

---

# 24. 推荐文件结构

signals/

macd_signal.py

cci_signal.py

entry_signal.py

---

# 25. 风控文件

risk/

position_sizer.py

stop_engine.py

tp_engine.py

cooldown_guard.py

---

# 26. 执行文件

execution/

order_manager.py

position_manager.py

exchange_adapter.py

---

# 27. 回测文件

backtest/

runner.py

broker.py

analyzer.py

---

# 28. 报告文件

reporting/

html_report.py

csv_exporter.py

excel_exporter.py

---

# 29. 测试目录

tests/

unit/

integration/

backtest/

---

# 30. 最终原则

策略负责判断

风控负责约束

执行负责执行

任何模块不得越权