from __future__ import annotations


def is_cooldown_active(now_ts: int, cooldown_until_ts: int | None) -> bool:
    return cooldown_until_ts is not None and now_ts < cooldown_until_ts
