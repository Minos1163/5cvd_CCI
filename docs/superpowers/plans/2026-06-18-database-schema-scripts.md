# Database Schema Scripts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the scripts required by `docs/15_database_schema.md`.

**Architecture:** Add a pure database-schema contract under `src/data/database_schema.py` that records the PostgreSQL-oriented table list, columns, indexes, write boundaries, idempotency keys, retention rules, and DDL rendering. Keep it side-effect free: no database connection, no migrations applied, no live data writes.

**Tech Stack:** Python standard library, dataclasses, pytest.

---

## Scope Notes

`docs/15_database_schema.md` requires a stable schema contract for symbols, candles, indicators, strategy events, signals, orders, fills, positions, risk/account snapshots, cooldowns, backtest tables, metrics, audit/report/config/event/system-health tables, plus naming, UTC time, write-boundary, idempotency, partitioning, retention, JSON-field, migration, and forbidden-pattern rules.

This plan implements deterministic schema metadata and SQL rendering. It does not connect to PostgreSQL, create production tables, add Redis/Object Storage, write migrations to a live database, or change strategy/execution behavior.

## File Structure

- Create: `src/data/database_schema.py` - database constants, table/column/index metadata, write boundaries, idempotency keys, DDL rendering, and schema validation.
- Create: `scripts/describe_database_schema.py` - prints the completed 15 database schema contract as JSON.
- Create: `tests/test_database_schema.py` - tests table inventory, required columns/indexes, write boundaries, idempotency, DDL rendering, and validation.
- Create: `tests/test_describe_database_schema.py` - tests describe script JSON output.
- Modify: `scripts/scaffold_ai300_framework.py` - sync templates for the new module, script, and tests.
- Preserve: `src/api/binance_client.py` - do not modify the stable Binance client.

---

### Task 1: Schema Inventory and Core Table Metadata

**Files:**
- Create: `src/data/database_schema.py`
- Create: `tests/test_database_schema.py`

- [ ] **Step 1: Write failing inventory tests**

Create `tests/test_database_schema.py` with assertions for `DATABASE_ENGINE`, `DATA_LAYERS`, `CORE_TABLES`, `COMMON_CORE_FIELDS`, `TABLE_SCHEMAS`, and `validate_schema_contract()`.

- [ ] **Step 2: Run failure**

Run: `pytest tests/test_database_schema.py -q`

Expected: FAIL because `src.data.database_schema` does not exist.

- [ ] **Step 3: Implement constants and table metadata**

Create dataclasses `Column`, `IndexSpec`, `TableSchema`, `SchemaValidationResult`. Define all 21 core tables from the doc and enough fields/indexes to make their ownership and query patterns explicit.

- [ ] **Step 4: Verify**

Run: `pytest tests/test_database_schema.py -q`

Expected: PASS for inventory tests.

---

### Task 2: DDL Rendering, Write Boundaries, Idempotency, and Retention

**Files:**
- Modify: `src/data/database_schema.py`
- Modify: `tests/test_database_schema.py`

- [ ] **Step 1: Add failing tests**

Append tests for `render_create_table()`, `WRITE_BOUNDARIES`, `IDEMPOTENCY_KEYS`, `PARTITIONED_TABLES`, `RETENTION_POLICY`, `JSON_FIELD_POLICY`, `MIGRATION_REQUIREMENTS`, `FORBIDDEN_DATABASE_PATTERNS`, and `EXTENSION_TABLES`.

- [ ] **Step 2: Run failure**

Run: `pytest tests/test_database_schema.py -q`

Expected: FAIL because these helpers/constants are incomplete.

- [ ] **Step 3: Implement helpers and policy constants**

Implement deterministic DDL string generation for known table metadata and contract constants from the doc.

- [ ] **Step 4: Verify**

Run: `pytest tests/test_database_schema.py -q`

Expected: PASS.

---

### Task 3: Describe Script

**Files:**
- Create: `scripts/describe_database_schema.py`
- Create: `tests/test_describe_database_schema.py`

- [ ] **Step 1: Add failing describe test**

Create `tests/test_describe_database_schema.py` that runs `python scripts/describe_database_schema.py` and validates the JSON payload.

- [ ] **Step 2: Run failure**

Run: `pytest tests/test_describe_database_schema.py -q`

Expected: FAIL because the describe script is missing.

- [ ] **Step 3: Implement describe script**

Create `scripts/describe_database_schema.py` that imports `src.data.database_schema` and prints table inventory, write boundaries, idempotency, retention, migration, and forbidden-pattern policy as JSON.

- [ ] **Step 4: Verify**

Run: `pytest tests/test_database_schema.py tests/test_describe_database_schema.py -q`

Expected: PASS.

---

### Task 4: Scaffold Sync and Verification

**Files:**
- Modify: `scripts/scaffold_ai300_framework.py`

- [ ] **Step 1: Sync scaffold templates**

Copy final contents into `scripts/scaffold_ai300_framework.py` for:

- `src/data/database_schema.py`
- `scripts/describe_database_schema.py`
- `tests/test_database_schema.py`
- `tests/test_describe_database_schema.py`

- [ ] **Step 2: Run targeted tests**

Run: `pytest tests/test_database_schema.py tests/test_describe_database_schema.py tests/test_framework_scaffold.py -q`

Expected: PASS.

- [ ] **Step 3: Run full verification**

Run:

```bash
pytest -q
python -m compileall src scripts tests
python scripts/describe_database_schema.py
git diff -- src/api/binance_client.py
```

Expected: all tests pass, compile succeeds, describe JSON includes completed 15 sections, and Binance diff has no output.

- [ ] **Step 4: Clean generated caches**

Run:

```powershell
$root=(Resolve-Path '.').Path; $targets=Get-ChildItem -Path . -Recurse -Directory -Filter '__pycache__' | Where-Object { $_.FullName.StartsWith($root) }; foreach($target in $targets){ Remove-Item -LiteralPath $target.FullName -Recurse -Force }; Get-ChildItem -Path . -Recurse -Directory -Filter '__pycache__' | Select-Object -ExpandProperty FullName
```

Expected: no remaining `__pycache__` directories in the workspace.

---

## Self-Review

- Spec coverage: covers database choice, data layers, naming/common fields, UTC policy, table inventory, table fields/indexes/unique keys, write boundaries, transaction/idempotency rules, partition/archive/retention policy, index and JSON rules, migration requirements, startup checks, query patterns, forbidden patterns, and extension tables.
- Placeholder scan: no `TBD`, `TODO`, `implement later`, or unspecified verification steps.
- Type consistency: `Column`, `IndexSpec`, `TableSchema`, `SchemaValidationResult`, `TABLE_SCHEMAS`, `render_create_table`, and `validate_schema_contract` are named consistently.
