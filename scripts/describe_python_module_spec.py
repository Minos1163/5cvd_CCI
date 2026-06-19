from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.module_spec import (
    ALLOWED_DEPENDENCY_CHAIN,
    BASE_INTERFACE_METHODS,
    CONTEXT_STATES,
    ENGINE_NAMES,
    EVENT_TYPES,
    FINAL_MODULE_STRUCTURE,
    FINAL_PRINCIPLE,
    FORBIDDEN_MODULE_PATTERNS,
    LAYER_RESPONSIBILITIES,
    RECOMMENDED_FILES,
    SIGNAL_OUTPUTS,
    STATE_MACHINE_STATES,
    TEST_DIRECTORIES,
)


def main() -> None:
    payload = {
        "final_module_structure": FINAL_MODULE_STRUCTURE,
        "layer_responsibilities": LAYER_RESPONSIBILITIES,
        "forbidden_patterns": FORBIDDEN_MODULE_PATTERNS,
        "allowed_dependency_chain": ALLOWED_DEPENDENCY_CHAIN,
        "base_interfaces": BASE_INTERFACE_METHODS,
        "context_states": CONTEXT_STATES,
        "signal_outputs": SIGNAL_OUTPUTS,
        "state_machine_states": STATE_MACHINE_STATES,
        "engine_names": ENGINE_NAMES,
        "event_types": EVENT_TYPES,
        "recommended_files": RECOMMENDED_FILES,
        "test_directories": TEST_DIRECTORIES,
        "final_principle": FINAL_PRINCIPLE,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
