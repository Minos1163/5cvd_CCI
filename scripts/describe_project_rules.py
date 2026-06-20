from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.project_spec import (
    BACKTEST_GOALS,
    CORE_DESIGN_GOALS,
    CORE_TIMEFRAMES,
    ENTRY_FORMS,
    FINAL_SYSTEM_TRAITS,
    IMPLEMENTATION_PRINCIPLES,
    INDICATOR_RESPONSIBILITIES as PROJECT_INDICATOR_RESPONSIBILITIES,
    LIVE_TRADING_GOALS,
    MODULE_DEPENDENCY_FLOW,
    OPERATIONAL_SUCCESS_STANDARDS,
    POSITION_GOALS,
    PROJECT_ENGLISH_NAME,
    PROJECT_NAME,
    PROJECT_NON_GOALS,
    PROJECT_OBJECTIVE,
    PROJECT_PRIORITY,
    RECOMMENDED_DEVELOPMENT_ORDER,
    REFERENCE_TIMEFRAMES,
    RISK_GOALS,
    SUCCESS_CRITERIA,
    SYSTEM_LAYERS,
    TIMEFRAME_ROLES as PROJECT_TIMEFRAME_ROLES,
    TRADING_DECISION_PRINCIPLES,
    TRADING_VENUE,
    UNIFIED_CONTRACTS,
)
from src.core.strategy_philosophy import (
    ALLOWED_TRADE_TYPES,
    ANTI_NOISE_RULES,
    ANTI_OVERFIT_RULES,
    CAPITAL_MANAGEMENT_PRINCIPLES,
    DECISION_PRIORITY,
    EXIT_PHILOSOPHY,
    FIRST_PRINCIPLES,
    INDICATOR_RESPONSIBILITIES,
    MARKET_STATES,
    PHILOSOPHY_FORBIDDEN_PATTERNS,
    STRATEGY_IDENTITY,
    STRATEGY_NON_GOALS,
    TIMEFRAME_ROLES,
    UNCERTAINTY_ACTIONS,
    UNCERTAINTY_FORBIDDEN_ACTIONS,
)
from src.data.universe_filter import (
    MAX_MISSING_BAR_RATIO,
    MAX_SPREAD_PCT,
    MAX_SYMBOLS,
    MAX_SYMBOLS_HARD_CAP,
    MEME_POLICY,
    MIN_LISTING_DAYS,
    RECOMMENDED_MIN_24H_VOLUME_USD,
    REQUIRED_TIMEFRAMES,
    UNIVERSE_SCOPE,
    UNIVERSE_STATUSES,
    UPDATE_FREQUENCY,
)


def main() -> None:
    payload = {
        "project": {
            "name": PROJECT_NAME,
            "english_name": PROJECT_ENGLISH_NAME,
            "objective": PROJECT_OBJECTIVE,
            "priority": PROJECT_PRIORITY,
            "trading_venue": TRADING_VENUE,
            "core_design_goals": CORE_DESIGN_GOALS,
            "core_timeframes": CORE_TIMEFRAMES,
            "reference_timeframes": REFERENCE_TIMEFRAMES,
            "timeframe_roles": PROJECT_TIMEFRAME_ROLES,
            "indicator_responsibilities": PROJECT_INDICATOR_RESPONSIBILITIES,
            "trading_decision_principles": TRADING_DECISION_PRINCIPLES,
            "entry_forms": ENTRY_FORMS,
            "non_goals": PROJECT_NON_GOALS,
            "risk_goals": RISK_GOALS,
            "position_goals": POSITION_GOALS,
            "backtest_goals": BACKTEST_GOALS,
            "live_trading_goals": LIVE_TRADING_GOALS,
            "system_layers": SYSTEM_LAYERS,
            "module_dependency_flow": MODULE_DEPENDENCY_FLOW,
            "unified_contracts": UNIFIED_CONTRACTS,
            "operational_success_standards": OPERATIONAL_SUCCESS_STANDARDS,
            "implementation_principles": IMPLEMENTATION_PRINCIPLES,
            "recommended_development_order": RECOMMENDED_DEVELOPMENT_ORDER,
            "final_system_traits": FINAL_SYSTEM_TRAITS,
            "success_criteria": SUCCESS_CRITERIA,
        },
        "philosophy": {
            "strategy_identity": STRATEGY_IDENTITY,
            "strategy_non_goals": STRATEGY_NON_GOALS,
            "first_principles": FIRST_PRINCIPLES,
            "market_states": MARKET_STATES,
            "timeframe_roles": TIMEFRAME_ROLES,
            "indicator_responsibilities": INDICATOR_RESPONSIBILITIES,
            "decision_priority": DECISION_PRIORITY,
            "allowed_trade_types": ALLOWED_TRADE_TYPES,
            "anti_noise_rules": ANTI_NOISE_RULES,
            "anti_overfit_rules": ANTI_OVERFIT_RULES,
            "capital_management_principles": CAPITAL_MANAGEMENT_PRINCIPLES,
            "exit_philosophy": EXIT_PHILOSOPHY,
            "uncertainty_actions": UNCERTAINTY_ACTIONS,
            "uncertainty_forbidden_actions": UNCERTAINTY_FORBIDDEN_ACTIONS,
            "forbidden_patterns": PHILOSOPHY_FORBIDDEN_PATTERNS,
        },
        "universe": {
            "scope": UNIVERSE_SCOPE,
            "max_symbols": MAX_SYMBOLS,
            "max_symbols_hard_cap": MAX_SYMBOLS_HARD_CAP,
            "min_24h_volume_usd": RECOMMENDED_MIN_24H_VOLUME_USD,
            "min_listing_days": MIN_LISTING_DAYS,
            "max_spread_pct": MAX_SPREAD_PCT,
            "max_missing_bar_ratio": MAX_MISSING_BAR_RATIO,
            "update_frequency": UPDATE_FREQUENCY,
            "required_timeframes": REQUIRED_TIMEFRAMES,
            "statuses": UNIVERSE_STATUSES,
            "meme_policy": MEME_POLICY,
            "max_simultaneous_positions": 5,
            "recommended_positions": 3,
            "single_symbol_exposure": 0.20,
            "refresh_time_utc": "00:00",
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
