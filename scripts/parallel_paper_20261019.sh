#!/usr/bin/env bash
# 并行 paper:同一批真实行情、同一份标的、两条仓位口径各跑一个纸面账本。
#
#   对照组 fib_pa_v1      -> 旧口径名义上限 equity * risk_pct / (stop_pct * leverage)
#   实验组 risk_first     -> 同样的 risk_pct,名义只受保证金/敞口约束
#
# 两路必须是**同一份标的清单**(--symbols 显式钉住),否则市值排名漂移会让
# 两路看到不同的入场机会,对比就失效了。
#
# 用法:
#   bash scripts/parallel_paper_20261019.sh              # 前台(会阻塞)
#   bash scripts/parallel_paper_20261019.sh > /tmp/pp.log 2>&1 &
#
# 产物:
#   $ROOT/logs_parallel/fib_pa_v1/{decisions.jsonl,paper/...}
#   $ROOT/logs_parallel/risk_first/{decisions.jsonl,paper/...}
#
# 对比:
#   python scripts/analysis/paper_parallel_compare_20261019.py

set -euo pipefail

REPO="${PARALLEL_PAPER_REPO:-D:/AIDCA/AI300-fwdlib}"
CODE="${PARALLEL_PAPER_CODE:-$(cd "$(dirname "$0")/.." && pwd)}"
ROOT="${PARALLEL_PAPER_OUT:-$REPO/logs_parallel}"
PY="${PARALLEL_PAPER_PY:-C:/Users/Huang/AppData/Local/Programs/Python/Python312/python.exe}"
PROXY="${PARALLEL_PAPER_PROXY:-http://127.0.0.1:12334}"

# 与 configs/entry_chain.dry_run_fib_pa_v1.json 的 dry_run_symbols 一致(钉住,不走市值排名)
SYMBOLS="BNBUSDT,XRPUSDT,SOLUSDT,TRXUSDT,HYPEUSDT,DOGEUSDT,ZECUSDT,XLMUSDT,ADAUSDT,XMRUSDT,LINKUSDT,CCUSDT,LABUSDT,TONUSDT"

# 请求超时。两路各自要拉 14 标的 × 4 周期 = 56 个请求,同时打满会把代理挤爆;
# 默认 10s 超时会 URLError,然后**静默退化成 synthetic 数据**
# (日志里 warmup.source=synthetic + reason DATA_POLLUTION_COOLDOWN)。调大到 30s。
TIMEOUT="${PARALLEL_PAPER_TIMEOUT:-30}"

# 两路启动错开,避免同时打满代理;两者都对齐同一根 15m 收盘 K,看到的仍是同一根 bar。
STAGGER_SECONDS="${PARALLEL_PAPER_STAGGER:-120}"

# 必须同时设置**小写**变量:urllib 的 getproxies_environment 只读 *_proxy 环境变量,
# 而本机会话里预置了一个 502 的沙箱代理(127.0.0.1:55964),只设大写盖不掉它,
# 结果就是 klines 请求 URLError → 静默退化成 synthetic 数据。
# 不需要代理的环境把 PARALLEL_PAPER_PROXY 置空即可。
if [ -n "$PROXY" ]; then
  export http_proxy="$PROXY" https_proxy="$PROXY"
  export HTTP_PROXY="$PROXY" HTTPS_PROXY="$PROXY"
fi

mkdir -p "$ROOT/fib_pa_v1" "$ROOT/risk_first"

start_arm() {
  local name="$1" cfg="$2"
  local out="$ROOT/$name"
  echo "[$(date -u +%FT%TZ)] start $name -> $out"
  "$PY" "$CODE/scripts/run_live_dry_run.py" \
    --config "configs/entry_chain.dry_run_${cfg}.json" \
    --market-data-source public-binance \
    --symbols "$SYMBOLS" \
    --public-kline-limit 240 \
    --http-timeout "$TIMEOUT" \
    --align-to-kline-close \
    --kline-interval-seconds 900 \
    --post-close-delay-seconds 10 \
    --interval-seconds 60 \
    --output-dir "$out" \
    --log-root "$out/dry_run" \
    --paper-state-dir "$out/paper" \
    >> "$out/stdout.log" 2>&1
}

# 注意:必须在 $CODE 下运行,保证两路用的是同一份代码(含 risk_first_sizing_enabled)
cd "$CODE"

start_arm fib_pa_v1 fib_pa_v1 &
PID_A=$!
sleep "$STAGGER_SECONDS"
start_arm risk_first risk_first &
PID_B=$!

trap 'kill $PID_A $PID_B 2>/dev/null || true' EXIT
wait $PID_A $PID_B
