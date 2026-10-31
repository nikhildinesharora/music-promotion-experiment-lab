import pandas as pd
import pytest

from music_promotion.reporting import choose_recommendation


def passing_summary():
    return pd.DataFrame(
        [
            {"metric": "qualified_listen_rate", "ci_lower": 0.03, "ci_upper": 0.05},
            {"metric": "skip_rate", "ci_lower": -0.01, "ci_upper": 0.005},
            {"metric": "repeat_7d_rate", "ci_lower": 0.01, "ci_upper": 0.02},
        ]
    )


def test_srm_failure_blocks_even_large_primary_effect():
    decision, _ = choose_recommendation(passing_summary(), {"passes_at_0_01": 0}, {"passes": True})
    assert decision.startswith("Investigate")


@pytest.mark.parametrize(
    "metric,column,value",
    [
        ("qualified_listen_rate", "ci_lower", 0.005),
        ("skip_rate", "ci_upper", 0.02),
        ("repeat_7d_rate", "ci_lower", -0.02),
        ("qualified_listen_rate", "ci_lower", float("nan")),
    ],
)
def test_benefit_and_guardrails_cannot_be_overridden(metric, column, value):
    summary = passing_summary()
    summary.loc[summary.metric.eq(metric), column] = value
    decision, _ = choose_recommendation(summary, {"passes_at_0_01": 1}, {"passes": True})
    assert decision.startswith("Hold")


def test_diversity_gate_and_passing_scenario():
    for passes, prefix in [(False, "Hold"), (True, "Scenario qualifies")]:
        decision, _ = choose_recommendation(
            passing_summary(), {"passes_at_0_01": 1}, {"passes": passes}
        )
        assert decision.startswith(prefix)
