#!/usr/bin/env bash
# 在 VPS 上跑"regime_overlay 影子":只写日志与独立纸面账本,不影响 systemd 上的生产实例。
#
# 生产实例用 logs/ 与 logs/state/paper;这里全部落到 logs_shadow/regime/ 下,
# 两套账本互不干扰。默认只记录(regime_overlay=shadow),不会拦任何开仓。
#
# 用法:
#   bash scripts/run_shadow_regime.sh                  # 前台跑(会阻塞,建议配合 tmux/screen)
#   PROXY=http://127.0.0.1:7890 bash scripts/run_shadow_regime.sh
#   nohup bash scripts/run_shadow_regime.sh >/tmp/shadow_regime.log 2>&1 &
#
# 可用环境变量:
#   CODE     仓库根(默认脚本上一级)
#   OUT      输出目录(默认 $CODE/logs_shadow/regime)
#   PY       python 解释器(默认 python3)
#   SYMBOLS  标的(默认 BTCUSDT,ETHUSDT,BNBUSDT)
#   CFG      配置(默认 configs/entry_chain.dry_run_regime_shadow.json)
#   PROXY    需要时填 http://host:port,会同时设大小写两套变量
set -euo pipefail

CODE="${CODE:-$(cd "$(dirname "$0")/.." && pwd)}"
OUT="${OUT:-$CODE/logs_shadow/regime}"
PY="${PY:-python3}"
SYMBOLS="${SYMBOLS:-BTCUSDT,ETHUSDT,BNBUSDT}"
CFG="${CFG:-configs/entry_chain.dry_run_regime_shadow.json}"
PROXY="${PROXY:-}"

cd "$CODE"

if [ ! -f "$CFG" ]; then
  echo "[error] 找不到配置 $CFG"
  echo "        请先更新代码到包含 regime_overlay 的版本:"
  echo "        git fetch origin C20261019 && git checkout C20261019 && git pull"
  exit 1
fi

if [ -n "$PROXY" ]; then
  export http_proxy="$PROXY" https_proxy="$PROXY" HTTP_PROXY="$PROXY" HTTPS_PROXY="$PROXY"
  echo "[proxy] $PROXY"
fi

mkdir -p "$OUT"
echo "[run] cfg=$CFG out=$OUT symbols=$SYMBOLS"

exec "$PY" scripts/run_live_dry_run.py \
  --config "$CFG" \
  --market-data-source public-binance \
  --symbols "$SYMBOLS" \
  --public-kline-limit 240 \
  --http-timeout 30 \
  --align-to-kline-close \
  --kline-interval-seconds 900 \
  --post-close-delay-seconds 10 \
  --interval-seconds 60 \
  --output-dir "$OUT" \
  --log-root "$OUT/dry_run" \
  --paper-state-dir "$OUT/state/paper"
