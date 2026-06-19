from pathlib import Path

from src.backtest.fill_model import next_bar_market_fill
from src.risk.position_sizer import reject_if_below_min_notional, size_notional
from src.state_machine.entry_state_machine import EntryState, transition
from scripts.scaffold_ai300_framework import FILES


def test_probe_is_quarter_direct():
    direct = size_notional(10000, 0.01, 0.02, "DIRECT")
    probe = size_notional(10000, 0.01, 0.02, "PROBE")
    assert probe == direct * 0.25


def test_probe_below_min_notional_rejects_instead_of_inflating():
    ok, reason = reject_if_below_min_notional(4.0, 5.0)
    assert ok is False
    assert "skip" in reason


def test_buy_slippage_increases_price():
    assert next_bar_market_fill(100.0, "BUY", 10) == 100.1


def test_valid_state_transition():
    assert transition(EntryState.FLAT, EntryState.WATCH_LONG) == EntryState.WATCH_LONG


def test_scaffold_includes_signal_engine_16_templates():
    assert "src/signals/signal_engine.py" in FILES
    assert "scripts/describe_signal_engine.py" in FILES
    assert "tests/test_signal_engine.py" in FILES
    assert "tests/test_describe_signal_engine.py" in FILES
    assert "SignalResult" in FILES["src/signals/signal_engine.py"]


def test_scaffold_includes_risk_engine_17_templates():
    assert "src/risk/risk_engine.py" in FILES
    assert "scripts/describe_risk_engine.py" in FILES
    assert "tests/test_risk_engine.py" in FILES
    assert "tests/test_describe_risk_engine.py" in FILES
    assert "RiskResult" in FILES["src/risk/risk_engine.py"]


def test_scaffold_includes_execution_engine_18_templates():
    assert "src/execution/execution_engine.py" in FILES
    assert "scripts/describe_execution_engine.py" in FILES
    assert "tests/test_execution_engine.py" in FILES
    assert "tests/test_describe_execution_engine.py" in FILES
    assert "ExecutionEngine" in FILES["src/execution/execution_engine.py"]


def test_scaffold_includes_backtest_engine_19_templates():
    assert "src/backtest/engine.py" in FILES
    assert "scripts/describe_backtest_engine.py" in FILES
    assert "tests/test_backtest_engine.py" in FILES
    assert "tests/test_describe_backtest_engine.py" in FILES
    assert "BacktestRequest" in FILES["src/backtest/engine.py"]
    assert "BACKTEST_STEP_ORDER" in FILES["src/backtest/engine.py"]


def test_scaffold_includes_deployment_architecture_20_templates():
    assert "src/deployment/deployment_architecture.py" in FILES
    assert "scripts/describe_deployment_architecture.py" in FILES
    assert "tests/test_deployment_architecture.py" in FILES
    assert "tests/test_describe_deployment_architecture.py" in FILES
    assert "DeploymentPlan" in FILES["src/deployment/deployment_architecture.py"]
    assert "PROTECTION_MODE_TRIGGERS" in FILES["src/deployment/deployment_architecture.py"]


def test_scaffold_includes_expanded_strategy_philosophy_templates():
    template = FILES["src/core/strategy_philosophy.py"]
    assert "STRATEGY_IDENTITY" in template
    assert "DECISION_PRIORITY" in template
    assert "PHILOSOPHY_FORBIDDEN_PATTERNS" in template
    assert "validate_uncertainty_response" in template
    assert "validate_long_short_symmetry" in template


def test_scaffold_templates_include_expanded_project_contract():
    content = Path("scripts/scaffold_ai300_framework.py").read_text(encoding="utf-8")
    assert 'PROJECT_NAME = "多周期主流虚拟币趋势交易系统"' in content
    assert '"background_reference_only"' in content
    assert '"position_sizing"' in content
    assert '"monitoring"' in content
    assert "stable_position_and_order_recovery" in content


def test_scaffold_still_protects_binance_client():
    content = Path("scripts/scaffold_ai300_framework.py").read_text(encoding="utf-8")
    assert "src/api/binance_client.py" in content
    assert "scaffold must not modify src/binance_client.py" in content
