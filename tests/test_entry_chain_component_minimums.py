from src.signals.entry_chain import check_component_minimums


def test_component_minimum_reason_names_component_and_gap():
    scores = {
        "price_action_structure": 3.5,
        "fibonacci_location": 18.0,
        "risk_reward_geometry": 4.0,
    }

    ok, reason = check_component_minimums(
        scores,
        "DIRECT",
        {"price_action_structure": 6.0},
    )

    assert ok is False
    assert reason == "DIRECT_BELOW_PRICE_ACTION_STRUCTURE_MINIMUM_GAP_2.5"


def test_component_minimum_passes_when_all_components_meet_threshold():
    scores = {
        "price_action_structure": 6.0,
        "fibonacci_location": 13.0,
        "risk_reward_geometry": 4.0,
    }

    ok, reason = check_component_minimums(
        scores,
        "DIRECT",
        {
            "price_action_structure": 6.0,
            "fibonacci_location": 6.0,
            "risk_reward_geometry": 2.0,
        },
    )

    assert ok is True
    assert reason == ""
