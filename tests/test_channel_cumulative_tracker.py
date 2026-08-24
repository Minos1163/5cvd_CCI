import scripts.channel_cumulative_tracker as tracker


def test_tracker_includes_proposed_shadow_channels():
    assert "scout_bnb_trend_continuation_after_pullback" in tracker.TRACKED_CHANNELS
    assert "scout_bull_regime_breakout_v1" in tracker.TRACKED_CHANNELS


def test_proposed_shadow_channels_are_scoped_to_scout_ledger():
    assert tracker.CHANNEL_LEDGER_SCOPE["scout_bnb_trend_continuation_after_pullback"] == (
        "scout_micro/paper_trades.jsonl",
    )
    assert tracker.CHANNEL_LEDGER_SCOPE["scout_bull_regime_breakout_v1"] == (
        "scout_micro/paper_trades.jsonl",
    )
