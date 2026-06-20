from __future__ import annotations


def main() -> None:
    win_rate = 0.65
    stop_pct = 0.015
    tp_levels = (1.0, 2.0, 3.0)
    tp_fractions = (0.40, 0.35, 0.25)
    fee_per_side = 0.0005

    avg_win_gross = sum(fraction * stop_pct * level for fraction, level in zip(tp_fractions, tp_levels))
    avg_loss_gross = -stop_pct
    round_trip_fee = fee_per_side + sum(fraction * fee_per_side for fraction in tp_fractions)
    expectancy = win_rate * avg_win_gross + (1 - win_rate) * avg_loss_gross - round_trip_fee

    print(f"avg_win_gross={avg_win_gross:.6f}")
    print(f"avg_loss_gross={avg_loss_gross:.6f}")
    print(f"round_trip_fee={round_trip_fee:.6f}")
    print(f"expectancy={expectancy:.6f}")

    if expectancy <= 0:
        raise SystemExit(f"negative lifecycle expectancy after fees: {expectancy:.6f}")


if __name__ == "__main__":
    main()
