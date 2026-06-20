# AI300 VPS Dry-Run Runbook

This runbook starts the strategy observer in dry-run mode. Dry-run writes decisions and order drafts only. It must not submit, cancel, or amend exchange orders.

## Install

```bash
cd /root
git clone https://github.com/Minos1163/5cvd_CCI.git AIBOT
cd /root/AIBOT
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
mkdir -p /root/AIBOT/logs
```

The systemd dry-run service aligns scans to completed Binance 15m candles. It waits for the 0/15/30/45 minute candle boundary plus 5 seconds before fetching klines and evaluating signals.

## Config Tiers

Start with conservative only unless explicitly running the latest research dry-run lane:

- `configs/entry_chain.dry_run_conservative.json`: safety validation, lower frequency, stricter thresholds.
- `configs/entry_chain.dry_run_balanced.json`: use only after 30 days of conservative dry-run meeting the conservative target.
- `configs/entry_chain.dry_run_aggressive.json`: research only; use only after manual review and at least 60 additional days of balanced dry-run.
- `configs/entry_chain.dry_run_highest_win.json`: current highest-win research entry profile, based on V5 combined entry configuration. Use for signal observation only, not live trading.

Default `configs/entry_chain.dry_run.json` matches conservative.

## Verify Safety

```bash
python scripts/vps_dry_run_healthcheck.py --config configs/entry_chain.dry_run_conservative.json --output-dir reports/dry_run/healthcheck
python scripts/vps_dry_run_healthcheck.py --config configs/entry_chain.dry_run_highest_win.json --output-dir reports/dry_run/highest_win_healthcheck
```

Required:

- `status` is `ok`
- `dry_run_safe` is `true`
- `forbidden_tokens` is empty

## One-Shot Smoke

```bash
python scripts/run_live_dry_run.py --config configs/entry_chain.dry_run_conservative.json --target-tier conservative --once --log-root /root/AIBOT/logs --symbols BNBUSDT,SOLUSDT
```

Highest-win public-market smoke:

```bash
python scripts/run_live_dry_run.py --config configs/entry_chain.dry_run_highest_win.json --target-tier aggressive --market-data-source public-binance --once --log-root /root/AIBOT/logs --symbols DOGEUSDT,SOLUSDT,ZECUSDT,XLMUSDT,BNBUSDT,TRXUSDT
```

Check:

```bash
TODAY_UTC=$(date -u +%F)
MONTH_UTC=$(date -u +%Y-%m)
LOG_DIR=/root/AIBOT/logs/$MONTH_UTC/$TODAY_UTC
ls -la "$LOG_DIR"
cat "$LOG_DIR/health.json"
cat "$LOG_DIR/summary.json"
```

Expected files:

- `decisions.jsonl`
- `order_drafts.jsonl`
- `attribution.jsonl`
- `gate_rejections.csv`
- `runtime.out.log`
- `health.json`
- `summary.json`
- `paper_positions.json`
- `paper_trades.jsonl`
- `paper_equity.json`
- `paper_summary.json`

`orders_submitted` must be `0`.

## Start Systemd Service

```bash
sudo cp deploy/systemd/aibot.service /etc/systemd/system/aibot.service
sudo systemctl daemon-reload
sudo systemctl enable aibot.service
sudo systemctl start aibot.service
sudo systemctl status aibot.service --no-pager
```

## View Logs

```bash
journalctl -u aibot.service -f
TODAY_UTC=$(date -u +%F)
MONTH_UTC=$(date -u +%Y-%m)
LOG_DIR=/root/AIBOT/logs/$MONTH_UTC/$TODAY_UTC
tail -f "$LOG_DIR/runtime.out.log"
tail -f "$LOG_DIR/decisions.jsonl"
tail -f "$LOG_DIR/attribution.jsonl"
tail -f "$LOG_DIR/paper_trades.jsonl"
cat "$LOG_DIR/paper_positions.json"
cat "$LOG_DIR/paper_equity.json"
cat "$LOG_DIR/paper_summary.json"
cat "$LOG_DIR/summary.json"
```

## Stop

```bash
sudo systemctl stop aibot.service
```

## Safety Notes

- Do not add API keys to repo files.
- Do not edit `src/api/binance_client.py` for dry-run.
- Do not replace dry-run scripts with live submission scripts until backtests, audit logs, and manual review pass.
- Highest-win dry-run uses public Binance Futures klines and still must show `orders_submitted = 0`.
- Use `docs/review_template.md` for every 30-day dry-run review.
- Do not promote to balanced or aggressive without manual review.
