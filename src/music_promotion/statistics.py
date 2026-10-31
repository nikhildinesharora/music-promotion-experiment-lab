from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class MetricSpec:
    key: str
    label: str
    numerator: str
    denominator: str | None = None


METRICS = (
    MetricSpec("qualified_listen_rate", "Qualified listen rate", "qualified_listen"),
    MetricSpec("play_rate", "Play rate", "played"),
    MetricSpec("save_rate", "Save rate", "saved"),
    MetricSpec("repeat_7d_rate", "Seven-day repeat rate", "repeated_7d"),
    MetricSpec("skip_rate", "Skip rate", "skipped", denominator="played"),
)


def _metric_totals(frame: pd.DataFrame, metric: MetricSpec) -> dict[str, tuple[float, float]]:
    totals: dict[str, tuple[float, float]] = {}
    for variant in ("control", "treatment"):
        arm = frame.loc[frame["assignment"].eq(variant)]
        numerator = float(arm[metric.numerator].sum())
        denominator = (
            float(arm[metric.denominator].sum()) if metric.denominator else float(len(arm))
        )
        totals[variant] = (numerator, denominator)
    return totals


def clustered_rate_effect(
    frame: pd.DataFrame,
    metric: MetricSpec,
    *,
    cluster_col: str = "listener_id",
    bootstrap_reps: int = 1_000,
    seed: int = 20261028,
) -> dict[str, float | int | str]:
    if bootstrap_reps < 30:
        raise ValueError("At least 30 bootstrap replicates are required.")
    if frame.empty or frame[cluster_col].nunique() < 2:
        raise ValueError("Inference requires at least two listener clusters.")
    if set(frame["assignment"].unique()) != {"control", "treatment"}:
        raise ValueError("Both valid assignment arms are required.")
    totals = _metric_totals(frame, metric)
    control_num, control_den = totals["control"]
    treatment_num, treatment_den = totals["treatment"]
    control_rate = control_num / control_den if control_den else float("nan")
    treatment_rate = treatment_num / treatment_den if treatment_den else float("nan")
    effect = treatment_rate - control_rate

    denominator_col = metric.denominator
    columns = [cluster_col, "assignment", metric.numerator]
    if denominator_col:
        columns.append(denominator_col)
    work = frame[columns].copy()
    work["denominator_value"] = work[denominator_col] if denominator_col else 1
    grouped = (
        work.groupby([cluster_col, "assignment"], observed=True)
        .agg(numerator=(metric.numerator, "sum"), denominator=("denominator_value", "sum"))
        .reset_index()
    )
    clusters = sorted(grouped[cluster_col].unique())
    index = {cluster: position for position, cluster in enumerate(clusters)}
    numerators = np.zeros((len(clusters), 2), dtype=float)
    denominators = np.zeros((len(clusters), 2), dtype=float)
    arm_index = {"control": 0, "treatment": 1}
    for row in grouped.itertuples(index=False):
        i = index[getattr(row, cluster_col)]
        j = arm_index[row.assignment]
        numerators[i, j] = row.numerator
        denominators[i, j] = row.denominator

    rng = np.random.default_rng(seed)
    effects = []
    for _ in range(bootstrap_reps):
        sampled = rng.integers(0, len(clusters), size=len(clusters))
        weights = np.bincount(sampled, minlength=len(clusters))
        boot_num = weights @ numerators
        boot_den = weights @ denominators
        if np.all(boot_den > 0):
            effects.append((boot_num[1] / boot_den[1]) - (boot_num[0] / boot_den[0]))

    boot = np.asarray(effects, dtype=float)
    if len(boot) < max(30, bootstrap_reps // 2):
        ci_low = ci_high = p_value = float("nan")
    else:
        ci_low, ci_high = np.quantile(boot, [0.025, 0.975])
        standard_error = float(boot.std(ddof=1))
        z_score = (
            abs(effect / standard_error)
            if standard_error > 0
            else (0.0 if effect == 0 else float("inf"))
        )
        p_value = math.erfc(z_score / math.sqrt(2))

    relative_lift = effect / control_rate if control_rate else float("nan")
    return {
        "metric": metric.key,
        "metric_label": metric.label,
        "control_rate": control_rate,
        "treatment_rate": treatment_rate,
        "absolute_lift": effect,
        "relative_lift": relative_lift,
        "ci_lower": float(ci_low),
        "ci_upper": float(ci_high),
        "p_value": float(p_value),
        "n_control": int(control_den),
        "n_treatment": int(treatment_den),
        "clusters": len(clusters),
    }


def sample_ratio_mismatch(
    frame: pd.DataFrame, treatment_share: float = 0.5
) -> dict[str, float | int]:
    if frame.empty or not 0 < treatment_share < 1:
        raise ValueError("SRM requires observations and an allocation strictly between 0 and 1.")
    if not frame["assignment"].isin(["control", "treatment"]).all():
        raise ValueError("Unknown or missing assignment.")
    treatment = int(frame["assignment"].eq("treatment").sum())
    control = int(frame["assignment"].eq("control").sum())
    total = treatment + control
    expected_treatment = total * treatment_share
    expected_control = total * (1 - treatment_share)
    chi_square = ((treatment - expected_treatment) ** 2 / expected_treatment) + (
        (control - expected_control) ** 2 / expected_control
    )
    p_value = math.erfc(math.sqrt(chi_square / 2))
    return {
        "control": control,
        "treatment": treatment,
        "treatment_share": treatment / total,
        "chi_square": chi_square,
        "p_value": p_value,
        "passes_at_0_01": int(p_value >= 0.01),
    }


def minimum_detectable_effect(
    control_rate: float,
    n_control: int,
    n_treatment: int,
    *,
    alpha: float = 0.05,
    power: float = 0.80,
) -> dict[str, float | int | str]:
    if not 0 < control_rate < 1 or min(n_control, n_treatment) <= 0:
        raise ValueError("MDE requires a baseline in (0, 1) and positive arm sizes.")
    if not 0 < alpha < 1 or not 0.5 < power < 1:
        raise ValueError("Invalid alpha or power.")
    effective_n = min(n_control, n_treatment)
    z_alpha = NormalDist().inv_cdf(1 - alpha / 2)
    z_power = NormalDist().inv_cdf(power)
    mde = (z_alpha + z_power) * math.sqrt(2 * control_rate * (1 - control_rate) / effective_n)
    return {
        "method": "IID Bernoulli planning approximation; ignores listener clustering",
        "control_rate": control_rate,
        "n_per_arm_conservative": effective_n,
        "alpha": alpha,
        "power": power,
        "absolute_mde": mde,
        "relative_mde": mde / control_rate if control_rate else float("nan"),
        "target_absolute_effect": 0.02,
        "required_per_arm_for_2pp": math.ceil(
            2 * control_rate * (1 - control_rate) * ((z_alpha + z_power) / 0.02) ** 2
        ),
    }


def benjamini_hochberg(p_values: pd.Series) -> pd.Series:
    valid = p_values.dropna().sort_values()
    adjusted = pd.Series(np.nan, index=p_values.index, dtype=float)
    if valid.empty:
        return adjusted

    count = len(valid)
    raw = valid.to_numpy() * count / np.arange(1, count + 1)
    monotone = np.minimum.accumulate(raw[::-1])[::-1].clip(max=1.0)
    adjusted.loc[valid.index] = monotone
    return adjusted


def artist_diversity(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for variant in ("control", "treatment"):
        played = frame.loc[frame["assignment"].eq(variant) & frame["played"].eq(1)]
        counts = played.groupby("artist_id").size()
        shares = counts / counts.sum()
        rows.append(
            {
                "assignment": variant,
                "played_tracks": int(len(played)),
                "unique_artists": int(counts.size),
                "unique_artists_per_1000_plays": (
                    counts.size / len(played) * 1000 if len(played) else float("nan")
                ),
                "artist_hhi": float((shares**2).sum()),
            }
        )
    return pd.DataFrame(rows)


def diversity_guardrail(frame: pd.DataFrame, bootstrap_reps: int, seed: int) -> dict:
    """Compare artist concentration with paired listener-cluster resampling."""
    listeners = sorted(frame["listener_id"].unique())
    artists = sorted(frame["artist_id"].unique())
    matrices = []
    for arm in ("control", "treatment"):
        plays = frame.loc[frame["assignment"].eq(arm) & frame["played"].eq(1)]
        counts = pd.crosstab(plays["listener_id"], plays["artist_id"])
        matrices.append(counts.reindex(index=listeners, columns=artists, fill_value=0).to_numpy())
    rng = np.random.default_rng(seed)
    weights = rng.multinomial(
        len(listeners), np.full(len(listeners), 1 / len(listeners)), size=bootstrap_reps
    )
    hhis = []
    for matrix in matrices:
        counts = weights @ matrix
        totals = counts.sum(axis=1)
        shares = np.divide(
            counts,
            totals[:, None],
            out=np.zeros_like(counts, dtype=float),
            where=totals[:, None] > 0,
        )
        hhis.append((shares**2).sum(axis=1))
    valid = (hhis[0] > 0) & (hhis[1] > 0)
    changes = hhis[1][valid] / hhis[0][valid] - 1
    if len(changes) < 30:
        raise ValueError("Insufficient played artists for diversity inference.")
    low, high = np.quantile(changes, [0.025, 0.975])
    point = artist_diversity(frame).set_index("assignment")["artist_hhi"]
    return {
        "relative_change": float(point["treatment"] / point["control"] - 1),
        "ci_lower": float(low),
        "ci_upper": float(high),
        "maximum_relative_increase": 0.10,
        "passes": bool(high <= 0.10),
    }
