from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backtest.engine import (
    BACKTEST_ANALYSIS_DIMENSIONS,
    BACKTEST_ARTIFACTS,
    BACKTEST_FAILURE_SAMPLE_TYPES,
    BACKTEST_FILL_MODELS,
    BACKTEST_FORBIDDEN_ACTIONS,
    BACKTEST_REQUIRED_EVENTS,
    BACKTEST_REQUIRED_INPUTS,
    BACKTEST_RESULT_FIELDS,
    BACKTEST_STEP_ORDER,
    BacktestBar,
    BacktestRequest,
    run_backtest,
)


def _sample_result() -> dict:
    request = BacktestRequest(
        run_id="describe-19",
        strategy_name="ai300",
        strategy_version="v1",
        config_version="cfg-1",
        data_version="data-1",
        symbols=["BTCUSDT"],
        timeframes=["15m", "30m", "1h", "4h"],
        start_time=0,
        end_time=2700,
        initial_capital=10_000,
        fee_model={"fee_bps": 5},
        slippage_model={"slippage_bps": 10},
        funding_model={},
        fill_model="NEXT_BAR_OPEN",
        capital_constraints={"notional_per_trade": 1_000},
        risk_constraints={},
        entry_modes=["PROBE", "DIRECT"],
        source="describe-script",
    )
    bars = {
        "BTCUSDT": [
            BacktestBar("BTCUSDT", 0, 100, 105, 95, 101, 10),
            BacktestBar("BTCUSDT", 900, 102, 107, 97, 103, 10),
            BacktestBar("BTCUSDT", 1800, 105, 110, 100, 106, 10),
        ]
    }

    def strategy(_request, _symbol, _bar, _context):
        return {
            "signal_type": "LONG",
            "signal_side": "LONG",
            "entry_mode": "DIRECT",
            "risk_allowed": True,
            "notional": 1_000,
        }

    result = run_backtest(request, bars, strategy_callback=strategy)
    return {
        "status": result.status,
        "trade_count": result.trade_count,
        "final_equity": result.final_equity,
        "degraded_assumptions": result.degraded_assumptions,
        "summary_json": result.summary_json,
    }


def main() -> None:
    payload = {
        "engine": "backtest_engine",
        "request_fields": BACKTEST_REQUIRED_INPUTS,
        "result_fields": BACKTEST_RESULT_FIELDS,
        "step_order": BACKTEST_STEP_ORDER,
        "fill_models": BACKTEST_FILL_MODELS,
        "required_events": BACKTEST_REQUIRED_EVENTS,
        "artifacts": BACKTEST_ARTIFACTS,
        "analysis_dimensions": BACKTEST_ANALYSIS_DIMENSIONS,
        "failure_sample_types": BACKTEST_FAILURE_SAMPLE_TYPES,
        "required_costs": ["fee", "slippage", "funding"],
        "forbidden_actions": BACKTEST_FORBIDDEN_ACTIONS,
        "sample_result": _sample_result(),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
