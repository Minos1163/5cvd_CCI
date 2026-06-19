from src.core.module_spec import (
    ALLOWED_DEPENDENCY_CHAIN,
    BASE_INTERFACE_METHODS,
    CONCEPTUAL_LAYER_IMPLEMENTATIONS,
    CONTEXT_STATES,
    ENGINE_NAMES,
    EVENT_TYPES,
    FINAL_MODULE_STRUCTURE,
    FORBIDDEN_MODULE_PATTERNS,
    LAYER_RESPONSIBILITIES,
    RECOMMENDED_FILES,
    SIGNAL_OUTPUTS,
    STATE_MACHINE_STATES,
    TEST_DIRECTORIES,
    BaseExecution,
    BaseIndicator,
    BaseRiskModel,
    BaseSignal,
    DTO,
    ModuleSpecCheck,
    StrategyContext,
    validate_dependency,
    validate_module_structure,
)


class ExampleSignal:
    def generate(self, context):
        return "WAIT"


class ExampleIndicator:
    def calculate(self, candles):
        return {"value": 1}


class ExampleRisk:
    def evaluate(self, signal, context):
        return {"approved": True}


class ExampleExecution:
    def submit(self, instruction):
        return {"status": "submitted"}

    def cancel(self, order_id):
        return {"status": "canceled"}

    def sync(self):
        return {"status": "synced"}


def test_final_module_structure_and_responsibilities_match_doc():
    assert FINAL_MODULE_STRUCTURE == [
        "config",
        "data",
        "indicators",
        "context",
        "signals",
        "state_machine",
        "risk",
        "execution",
        "portfolio",
        "backtest",
        "reporting",
        "observability",
        "deployment",
        "utils",
    ]
    assert LAYER_RESPONSIBILITIES["config"] == ["load_config", "validate_config", "freeze_config"]
    assert LAYER_RESPONSIBILITIES["data"] == ["fetch_data", "cache_data", "normalize_data"]
    assert LAYER_RESPONSIBILITIES["indicators"] == ["calculate_indicators", "output_results"]
    assert LAYER_RESPONSIBILITIES["context"] == ["multi_timeframe_market_state"]
    assert LAYER_RESPONSIBILITIES["execution"] == ["execute_approved_intent", "order_lifecycle", "position_sync"]
    assert LAYER_RESPONSIBILITIES["portfolio"] == ["account_management", "portfolio_risk", "position_sync"]
    assert LAYER_RESPONSIBILITIES["observability"] == ["logging", "metrics", "monitoring"]
    assert LAYER_RESPONSIBILITIES["deployment"] == ["startup", "shutdown", "recovery", "release_gates"]
    assert FORBIDDEN_MODULE_PATTERNS == ["cross_layer_overreach", "circular_dependency", "god_utility_class"]


def test_dependency_chain_allows_forward_flow_and_rejects_reverse_flow():
    assert ALLOWED_DEPENDENCY_CHAIN == [
        "data",
        "indicators",
        "context",
        "signals",
        "state_machine",
        "risk",
        "position_sizing",
        "execution",
        "backtest",
        "reporting",
        "monitoring",
    ]
    assert validate_dependency("data", "indicators") == ModuleSpecCheck(True, "dependency approved")
    assert validate_dependency("signals", "risk") == ModuleSpecCheck(True, "dependency approved")
    assert validate_dependency("risk", "position_sizing") == ModuleSpecCheck(True, "dependency approved")
    assert validate_dependency("position_sizing", "execution") == ModuleSpecCheck(True, "dependency approved")
    assert validate_dependency("execution", "signals").passed is False
    assert validate_dependency("risk", "backtest").passed is False
    assert validate_dependency("monitoring", "execution").passed is False


def test_validate_module_structure_accepts_current_src_directories():
    assert validate_module_structure("src").passed is True


def test_base_protocols_are_runtime_checkable_by_required_methods():
    assert isinstance(ExampleSignal(), BaseSignal)
    assert isinstance(ExampleIndicator(), BaseIndicator)
    assert isinstance(ExampleRisk(), BaseRiskModel)
    assert isinstance(ExampleExecution(), BaseExecution)
    assert BASE_INTERFACE_METHODS == {
        "BaseSignal": ["generate"],
        "BaseIndicator": ["calculate"],
        "BaseRiskModel": ["evaluate"],
        "BaseExecution": ["submit", "cancel", "sync"],
    }


def test_context_signal_state_engine_event_and_dto_contracts():
    assert CONTEXT_STATES == ["BULL", "BEAR", "NEUTRAL"]
    assert SIGNAL_OUTPUTS == ["LONG", "SHORT", "WAIT"]
    assert STATE_MACHINE_STATES == ["FLAT", "WATCH", "PROBE", "DIRECT", "MANAGE", "EXIT"]
    assert ENGINE_NAMES == ["market_engine", "signal_engine", "risk_engine", "execution_engine", "report_engine"]
    assert EVENT_TYPES == ["SIGNAL_CREATED", "ORDER_FILLED", "STOP_HIT", "TP_HIT"]
    context = StrategyContext(
        symbol="BTCUSDT",
        timeframe="15m",
        indicators={"macd": 1},
        state="WATCH",
        risk={"risk_per_trade_pct": 0.01},
    )
    dto = DTO(name="SignalDTO", payload={"side": "LONG"})
    assert context.symbol == "BTCUSDT"
    assert dto.payload["side"] == "LONG"


def test_recommended_files_and_test_directories_match_doc():
    assert RECOMMENDED_FILES["signals"] == ["macd_signal.py", "cci_signal.py", "entry_signal.py"]
    assert RECOMMENDED_FILES["risk"] == ["position_sizer.py", "stop_engine.py", "tp_engine.py", "cooldown_guard.py"]
    assert RECOMMENDED_FILES["execution"] == ["order_manager.py", "position_manager.py", "exchange_adapter.py"]
    assert RECOMMENDED_FILES["backtest"] == ["runner.py", "broker.py", "analyzer.py"]
    assert RECOMMENDED_FILES["reporting"] == ["html_report.py", "csv_exporter.py", "excel_exporter.py"]
    assert TEST_DIRECTORIES == ["tests/unit", "tests/integration", "tests/backtest"]


def test_conceptual_layer_implementations_bridge_current_file_layout():
    assert CONCEPTUAL_LAYER_IMPLEMENTATIONS == {
        "position_sizing": "src/risk/position_sizer.py",
        "monitoring": "src/observability/logging_metrics.py",
        "deployment": "src/deployment/deployment_architecture.py",
    }
