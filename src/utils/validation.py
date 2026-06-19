from __future__ import annotations


def require_positive(value: float, name: str) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be positive")
