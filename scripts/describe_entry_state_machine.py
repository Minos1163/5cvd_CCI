from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.state_machine.entry_state_machine import ALLOWED_TRANSITIONS, EntryState


def main() -> None:
    payload = {
        "initial_state": EntryState.FLAT.value,
        "states": [state.value for state in EntryState],
        "probe_upgrade_r": 1.0,
        "allowed_transitions": {
            state.value: sorted(target.value for target in targets)
            for state, targets in ALLOWED_TRANSITIONS.items()
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
