import pandas as pd
import pytest

from music_promotion.simulation import build_demo_contexts, simulate_campaign
from music_promotion.statistics import (
    METRICS,
    benjamini_hochberg,
    clustered_rate_effect,
    minimum_detectable_effect,
    sample_ratio_mismatch,
)


def experiment_frame(rows=4_000):
    contexts, _ = build_demo_contexts(n_rows=rows, seed=21)
    outcomes = simulate_campaign(contexts, seed=21, version="test")
    return contexts.merge(outcomes, on="experiment_id", validate="one_to_one")


def test_clustered_effect_recovers_positive_play_lift():
    result = clustered_rate_effect(experiment_frame(), METRICS[1], bootstrap_reps=200, seed=21)
    assert result["absolute_lift"] > 0.05
    assert result["ci_lower"] < result["ci_upper"]
    assert result["clusters"] >= 80


def test_srm_check_accepts_deterministic_assignment():
    result = sample_ratio_mismatch(experiment_frame())
    assert result["passes_at_0_01"] == 1
    assert 0.47 < result["treatment_share"] < 0.53


def test_benjamini_hochberg_is_monotone_in_sorted_order():
    values = pd.Series([0.04, 0.002, 0.03, 0.20])
    adjusted = benjamini_hochberg(values)
    ordered = adjusted.loc[values.sort_values().index]
    assert ordered.is_monotonic_increasing
    assert (adjusted >= values).all()


def test_zero_outcome_is_not_significant():
    frame = experiment_frame()
    frame["qualified_listen"] = 0
    result = clustered_rate_effect(frame, METRICS[0], bootstrap_reps=100)
    assert result["absolute_lift"] == result["ci_lower"] == result["ci_upper"] == 0
    assert result["p_value"] == 1


def test_srm_detects_broken_allocation_and_rejects_missing_labels():
    broken = pd.DataFrame({"assignment": ["control"] * 90 + ["treatment"] * 10})
    assert sample_ratio_mismatch(broken)["passes_at_0_01"] == 0
    with pytest.raises(ValueError):
        sample_ratio_mismatch(pd.DataFrame({"assignment": [None]}))


def test_mde_obeys_sample_size_scaling():
    small = minimum_detectable_effect(0.5, 1000, 1000)
    large = minimum_detectable_effect(0.5, 4000, 4000)
    assert small["absolute_mde"] == pytest.approx(2 * large["absolute_mde"])
    assert large["required_per_arm_for_2pp"] > 9000
