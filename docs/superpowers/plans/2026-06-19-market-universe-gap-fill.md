# Market Universe Gap Fill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the refreshed `docs/02_market_universe.md` into a clean, testable Market Universe risk-control contract.

**Architecture:** Keep this as a contract-first pass. Clean the markdown, expand the universe filter data structures and validation helpers, synchronize config/describe/scaffold templates, and add tests. Do not add live network calls, do not modify `src/api/binance_client.py`, and do not alter signal/risk/execution behavior until the universe contract is stable.

**Tech Stack:** Python dataclasses, pure validation functions, pytest, YAML config text, JSON describe scripts.

---

## File Structure

Modify:

- `docs/02_market_universe.md`  
  Clean wrapper text and keep only the section 02 Market Universe spec.

- `src/data/universe_filter.py`  
  Add V1 thresholds, richer candidate/member/snapshot structures, status handling, and validation helpers.

- `tests/test_market_universe.py`  
  Add tests for the refreshed 02 contract.

- `configs/universe.yaml`  
  Add V1 filter thresholds and update cadence.

- `src/config/config_schema.py`  
  Require the new universe config fields.

- `scripts/describe_project_rules.py`  
  Export the universe contract in machine-readable JSON.

- `tests/test_describe_project_rules.py`  
  Assert the describe output includes the expanded universe contract.

- `scripts/scaffold_ai300_framework.py`  
  Sync scaffold templates for the changed files.

- `tests/test_framework_scaffold.py`  
  Verify scaffold templates include the expanded universe contract.

Future follow-up, not required in this first pass:

- `src/data/database_schema.py`
- `tests/test_database_schema.py`
- `src/backtest/engine.py`
- `tests/test_backtest_engine.py`

---

## Shared Contract Decisions

Use these constants:

```python
UNIVERSE_SCOPE = "binance_usdt_perpetual"
MAX_SYMBOLS = 20
MAX_SYMBOLS_HARD_CAP = 30
RECOMMENDED_MIN_24H_VOLUME_USD = 300_000_000
MIN_LISTING_DAYS = 365
MAX_SPREAD_PCT = 0.05
MAX_MISSING_BAR_RATIO = 0.005
UPDATE_FREQUENCY = "weekly"
REQUIRED_TIMEFRAMES = ("15m", "30m", "1h", "4h")
UNIVERSE_STATUSES = ("ACTIVE", "SUSPENDED", "REMOVED")
```

Use this policy decision for meme assets:

```python
MEME_POLICY = "exclude_by_default_even_if_large_cap"
```

This keeps the current system aligned with the project non-goal of not being a meme-coin rotation system. The example list in the doc is illustrative, not a hard allowlist.

---

### Task 1: Clean Market Universe Markdown

**Files:**

- Modify: `docs/02_market_universe.md`

- [ ] **Step 1: Inspect current wrapper**

Run:

```powershell
Get-Content docs\02_market_universe.md -TotalCount 20
Select-String -Path docs\02_market_universe.md -Pattern "下面这个版本|````md|我建议你接下来" -Context 1,1
```

Expected: output shows wrapper text and outer markdown fence.

- [ ] **Step 2: Clean the document**

Edit `docs/02_market_universe.md` so:

- Line 1 is exactly `# Market Universe`.
- The file keeps the numbered Market Universe sections.
- The outer ````md fence is removed.
- The trailing "我建议你接下来让 Codex..." section is removed.
- Inner code fences remain valid markdown.

- [ ] **Step 3: Verify**

Run:

```powershell
$first = Get-Content docs\02_market_universe.md -TotalCount 1
if ($first -ne "# Market Universe") { throw "unexpected first line: $first" }
Select-String -Path docs\02_market_universe.md -Pattern "下面这个版本|````md|我建议你接下来" -Quiet
```

Expected: first check succeeds and final command prints `False`.

- [ ] **Step 4: Commit**

```powershell
git add docs\02_market_universe.md
git commit -m "docs: clean market universe contract"
```

Expected: commit succeeds.

---

### Task 2: Expand Universe Contract Module

**Files:**

- Modify: `src/data/universe_filter.py`
- Modify: `tests/test_market_universe.py`

- [ ] **Step 1: Add failing tests for V1 thresholds and candidate fields**

Append to `tests/test_market_universe.py`:

```python
from src.data.universe_filter import (
    MAX_MISSING_BAR_RATIO,
    MAX_SPREAD_PCT,
    MAX_SYMBOLS,
    MAX_SYMBOLS_HARD_CAP,
    MIN_LISTING_DAYS,
    RECOMMENDED_MIN_24H_VOLUME_USD,
    REQUIRED_TIMEFRAMES,
    UNIVERSE_SCOPE,
    UNIVERSE_STATUSES,
    UniverseMember,
    UniverseSnapshot,
    build_universe_snapshot,
    validate_candidate,
    validate_snapshot_for_backtest,
)


def test_universe_v1_thresholds_match_doc():
    assert UNIVERSE_SCOPE == "binance_usdt_perpetual"
    assert MAX_SYMBOLS == 20
    assert MAX_SYMBOLS_HARD_CAP == 30
    assert RECOMMENDED_MIN_24H_VOLUME_USD == 300_000_000
    assert MIN_LISTING_DAYS == 365
    assert MAX_SPREAD_PCT == 0.05
    assert MAX_MISSING_BAR_RATIO == 0.005
    assert REQUIRED_TIMEFRAMES == ("15m", "30m", "1h", "4h")
    assert UNIVERSE_STATUSES == ("ACTIVE", "SUSPENDED", "REMOVED")


def test_validate_candidate_rejects_spread_missing_history_and_monitoring_tag():
    good = UniverseCandidate(
        "BTCUSDT",
        market_cap_rank=1,
        volume_24h=1_000_000_000,
        price=50_000,
        listed_days=1000,
        contract_type="USDT_PERPETUAL",
        quote_asset="USDT",
        volume_rank=1,
        spread_pct=0.03,
        missing_bar_ratio=0.0,
        timeframes=("15m", "30m", "1h", "4h"),
    )
    assert validate_candidate(good).passed is True

    wide = good.with_updates(symbol="WIDEUSDT", spread_pct=0.20)
    assert validate_candidate(wide).passed is False

    missing = good.with_updates(symbol="MISSUSDT", missing_bar_ratio=0.01)
    assert validate_candidate(missing).passed is False

    monitored = good.with_updates(symbol="TAGUSDT", monitoring_tag=True)
    assert validate_candidate(monitored).passed is False
```

- [ ] **Step 2: Add failing tests for snapshots and historical backtest guard**

Append:

```python
def test_universe_snapshot_tracks_version_status_and_reasons():
    member = UniverseMember(
        symbol="BTCUSDT",
        market_cap_rank=1,
        volume_rank=1,
        status="ACTIVE",
        added_time=1_700_000_000,
        removed_time=None,
        version="2026W01",
        reason="passes_v1_filters",
    )
    snapshot = build_universe_snapshot("2026W01", [member], created_at=1_700_000_000)

    assert snapshot.version == "2026W01"
    assert snapshot.active_symbols() == ["BTCUSDT"]
    assert snapshot.members[0].reason == "passes_v1_filters"


def test_backtest_must_use_historical_universe_version():
    snapshot = UniverseSnapshot(
        version="2026W01",
        members=[],
        created_at=1_700_000_000,
        effective_from=1_700_000_000,
        effective_to=1_700_604_800,
        update_reason="weekly_refresh",
    )
    assert validate_snapshot_for_backtest(snapshot, backtest_start=1_700_100_000).passed is True
    assert validate_snapshot_for_backtest(snapshot, backtest_start=1_600_000_000).passed is False
```

- [ ] **Step 3: Run tests and confirm failure**

Run:

```powershell
pytest tests\test_market_universe.py -q
```

Expected: FAIL because the new constants/classes/helpers do not exist.

- [ ] **Step 4: Implement minimal contract**

Update `src/data/universe_filter.py`:

```python
from dataclasses import dataclass, replace


UNIVERSE_SCOPE = "binance_usdt_perpetual"
MAX_SYMBOLS = 20
MAX_SYMBOLS_HARD_CAP = 30
RECOMMENDED_MIN_24H_VOLUME_USD = 300_000_000
MIN_LISTING_DAYS = 365
MAX_SPREAD_PCT = 0.05
MAX_MISSING_BAR_RATIO = 0.005
UPDATE_FREQUENCY = "weekly"
REQUIRED_TIMEFRAMES = ("15m", "30m", "1h", "4h")
UNIVERSE_STATUSES = ("ACTIVE", "SUSPENDED", "REMOVED")
MEME_POLICY = "exclude_by_default_even_if_large_cap"


@dataclass(frozen=True)
class UniverseCheck:
    passed: bool
    reason: str


@dataclass(frozen=True)
class UniverseMember:
    symbol: str
    market_cap_rank: int
    volume_rank: int
    status: str
    added_time: int
    removed_time: int | None
    version: str
    reason: str


@dataclass(frozen=True)
class UniverseSnapshot:
    version: str
    members: list[UniverseMember]
    created_at: int
    effective_from: int
    effective_to: int | None
    update_reason: str

    def active_symbols(self) -> list[str]:
        return [member.symbol for member in self.members if member.status == "ACTIVE"]
```

Extend `UniverseCandidate` with optional fields and a `with_updates()` helper:

```python
    contract_type: str = "USDT_PERPETUAL"
    quote_asset: str = "USDT"
    volume_rank: int = 0
    spread_pct: float = 0.0
    missing_bar_ratio: float = 0.0
    timeframes: tuple[str, ...] = REQUIRED_TIMEFRAMES
    monitoring_tag: bool = False
    abnormal_wick_count: int = 0

    def with_updates(self, **updates) -> "UniverseCandidate":
        return replace(self, **updates)
```

Add helpers:

```python
def validate_candidate(candidate: UniverseCandidate) -> UniverseCheck:
    symbol = normalize_symbol(candidate.symbol)
    if not symbol.endswith("USDT") or candidate.quote_asset != "USDT":
        return UniverseCheck(False, "only USDT symbols are allowed")
    if candidate.contract_type != "USDT_PERPETUAL":
        return UniverseCheck(False, "only USDT perpetual contracts are allowed")
    if candidate.market_cap_rank > MAX_SYMBOLS_HARD_CAP:
        return UniverseCheck(False, "market cap rank outside hard cap")
    if candidate.volume_24h < RECOMMENDED_MIN_24H_VOLUME_USD:
        return UniverseCheck(False, "24h volume below V1 threshold")
    if candidate.listed_days < MIN_LISTING_DAYS:
        return UniverseCheck(False, "listing age below V1 threshold")
    if candidate.spread_pct > MAX_SPREAD_PCT:
        return UniverseCheck(False, "spread too wide")
    if candidate.missing_bar_ratio > MAX_MISSING_BAR_RATIO:
        return UniverseCheck(False, "missing bar ratio too high")
    if set(REQUIRED_TIMEFRAMES) - set(candidate.timeframes):
        return UniverseCheck(False, "missing required timeframe history")
    if candidate.delisting or candidate.monitoring_tag:
        return UniverseCheck(False, "delisting or monitoring risk")
    if candidate.is_meme or symbol in DEFAULT_EXCLUDED_MEME:
        return UniverseCheck(False, MEME_POLICY)
    if candidate.abnormal_wick_count > 0:
        return UniverseCheck(False, "abnormal wick risk")
    return UniverseCheck(True, "candidate approved")


def build_universe_snapshot(version: str, members: list[UniverseMember], created_at: int) -> UniverseSnapshot:
    return UniverseSnapshot(
        version=version,
        members=members,
        created_at=created_at,
        effective_from=created_at,
        effective_to=None,
        update_reason="weekly_refresh",
    )


def validate_snapshot_for_backtest(snapshot: UniverseSnapshot, backtest_start: int) -> UniverseCheck:
    if snapshot.effective_from > backtest_start:
        return UniverseCheck(False, "snapshot starts after backtest period")
    if snapshot.effective_to is not None and snapshot.effective_to < backtest_start:
        return UniverseCheck(False, "snapshot ended before backtest period")
    return UniverseCheck(True, "historical universe snapshot approved")
```

Update `filter_universe()` to call `validate_candidate()` by default.

- [ ] **Step 5: Run market-universe tests**

Run:

```powershell
pytest tests\test_market_universe.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src\data\universe_filter.py tests\test_market_universe.py
git commit -m "feat: expand market universe contract"
```

Expected: commit succeeds.

---

### Task 3: Sync Universe Config Schema

**Files:**

- Modify: `configs/universe.yaml`
- Modify: `src/config/config_schema.py`
- Modify: `tests/test_config_schema.py`

- [ ] **Step 1: Add failing config tests**

Append to `tests/test_config_schema.py`:

```python
def test_universe_config_requires_v1_market_universe_fields():
    required = CONFIG_REQUIRED_FIELDS["universe.yaml"]
    assert "universe.update_frequency" in required
    assert "universe.min_24h_volume_usd" in required
    assert "universe.min_listing_days" in required
    assert "universe.max_spread_pct" in required
    assert "universe.max_missing_bar_ratio" in required
    assert "universe.universe_version" in required
```

- [ ] **Step 2: Run config tests and confirm failure**

Run:

```powershell
pytest tests\test_config_schema.py -q
```

Expected: FAIL because required fields and config values are missing.

- [ ] **Step 3: Update `configs/universe.yaml`**

Use:

```yaml
version: 1.0.0
universe:
  exchange: binance_futures
  contract_type: USDT_PERPETUAL
  quote_asset: USDT
  max_symbols: 20
  max_symbols_hard_cap: 30
  min_market_cap_rank: 20
  max_market_cap_rank: 30
  min_24h_volume_usd: 300000000
  min_listing_days: 365
  max_spread_pct: 0.05
  max_missing_bar_ratio: 0.005
  update_frequency: weekly
  universe_version: 2026W01
  symbols:
    - BTCUSDT
    - ETHUSDT
    - BNBUSDT
    - SOLUSDT
    - XRPUSDT
```

- [ ] **Step 4: Update config schema required fields**

Add to `CONFIG_REQUIRED_FIELDS["universe.yaml"]`:

```python
"universe.contract_type",
"universe.quote_asset",
"universe.max_symbols_hard_cap",
"universe.min_market_cap_rank",
"universe.max_market_cap_rank",
"universe.min_24h_volume_usd",
"universe.min_listing_days",
"universe.max_spread_pct",
"universe.max_missing_bar_ratio",
"universe.update_frequency",
"universe.universe_version",
```

- [ ] **Step 5: Run config tests**

Run:

```powershell
pytest tests\test_config_schema.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add configs\universe.yaml src\config\config_schema.py tests\test_config_schema.py
git commit -m "feat: require market universe config thresholds"
```

Expected: commit succeeds.

---

### Task 4: Expand Describe Output And Scaffold

**Files:**

- Modify: `scripts/describe_project_rules.py`
- Modify: `tests/test_describe_project_rules.py`
- Modify: `scripts/scaffold_ai300_framework.py`
- Modify: `tests/test_framework_scaffold.py`

- [ ] **Step 1: Add failing describe test**

Append to `tests/test_describe_project_rules.py`:

```python
def test_describe_project_rules_outputs_expanded_market_universe_contract():
    result = subprocess.run(
        [sys.executable, "scripts/describe_project_rules.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    universe = payload["universe"]
    assert universe["scope"] == "binance_usdt_perpetual"
    assert universe["max_symbols"] == 20
    assert universe["max_symbols_hard_cap"] == 30
    assert universe["min_24h_volume_usd"] == 300000000
    assert universe["min_listing_days"] == 365
    assert universe["max_spread_pct"] == 0.05
    assert universe["required_timeframes"] == ["15m", "30m", "1h", "4h"]
    assert universe["statuses"] == ["ACTIVE", "SUSPENDED", "REMOVED"]
```

- [ ] **Step 2: Update describe imports and payload**

Import universe constants from `src.data.universe_filter` and replace the hardcoded universe payload with those constants.

- [ ] **Step 3: Sync scaffold templates**

Use the existing scaffold-sync pattern in this repository. Ensure these template strings include the expanded universe contract:

- `src/data/universe_filter.py`
- `tests/test_market_universe.py`
- `configs/universe.yaml`
- `src/config/config_schema.py`
- `tests/test_config_schema.py`
- `scripts/describe_project_rules.py`
- `tests/test_describe_project_rules.py`

- [ ] **Step 4: Add scaffold assertion**

Append to `tests/test_framework_scaffold.py`:

```python
def test_scaffold_includes_expanded_market_universe_templates():
    template = FILES["src/data/universe_filter.py"]
    assert "UNIVERSE_SCOPE" in template
    assert "UniverseSnapshot" in template
    assert "validate_snapshot_for_backtest" in template
    assert "MAX_MISSING_BAR_RATIO" in template
```

- [ ] **Step 5: Run describe and scaffold tests**

Run:

```powershell
pytest tests\test_describe_project_rules.py tests\test_framework_scaffold.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add scripts\describe_project_rules.py tests\test_describe_project_rules.py scripts\scaffold_ai300_framework.py tests\test_framework_scaffold.py
git commit -m "feat: describe expanded market universe contract"
```

Expected: commit succeeds.

---

### Task 5: Final Verification

**Files:**

- No planned source edits.

- [ ] **Step 1: Run targeted tests**

Run:

```powershell
pytest tests\test_market_universe.py tests\test_config_schema.py tests\test_describe_project_rules.py tests\test_framework_scaffold.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full tests and compile**

Run:

```powershell
pytest -q
python -m compileall src scripts tests
```

Expected: PASS.

- [ ] **Step 3: Confirm Binance client untouched**

Run:

```powershell
git diff -- src\api\binance_client.py
```

Expected: no output.

- [ ] **Step 4: Commit any verification-only test sync if needed**

Only commit if a directly related test needed synchronization. Do not commit unrelated changes.

---

## Non-Goals

- Do not fetch live market-cap data.
- Do not add external API dependencies.
- Do not change signal generation behavior.
- Do not change live execution behavior.
- Do not modify `src/api/binance_client.py`.
- Do not run a strategy backtest as part of this pass.

---

## Completion Criteria

- `docs/02_market_universe.md` is clean markdown.
- Universe contract exposes V1 thresholds and status lifecycle.
- Candidate validation covers liquidity, listing age, spread, missing bars, timeframes, monitoring/delisting, abnormal wick risk, and meme policy.
- Universe snapshots support versioned historical backtest selection.
- Config schema requires V1 universe thresholds.
- Describe output exports the universe contract.
- Scaffold templates match the implemented contract.
- Targeted and full tests pass.
- `git diff -- src\api\binance_client.py` has no output.

