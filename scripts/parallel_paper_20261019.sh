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

export HTTPS_PROXY="$PROXY" HTTP_PROXY="$PROXY"

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
start_arm risk_first risk_first &
PID_B=$!

trap 'kill $PID_A $PID_B 2>/dev/null || true' EXIT
wait $PID_A $PID_B
