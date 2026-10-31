from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from music_promotion.config import (  # noqa: E402
    DEFAULT_BOOTSTRAP_REPS,
    DEFAULT_SEED,
    DUCKDB_PATH,
    PROCESSED_METADATA_PATH,
)
from music_promotion.reporting import write_dashboard_data, write_decision_memo  # noqa: E402
from music_promotion.statistics import (  # noqa: E402
    METRICS,
    artist_diversity,
    benjamini_hochberg,
    clustered_rate_effect,
    diversity_guardrail,
    minimum_detectable_effect,
    sample_ratio_mismatch,
)

SEGMENT_DIMENSIONS = (
    "listener_segment",
    "track_age_segment",
    "artist_popularity_segment",
)


def _load_fact_table(database: Path, target: str = "local") -> pd.DataFrame:
    if target == "bigquery":
        from google.cloud import bigquery

        project = os.environ.get("GCP_PROJECT_ID", "music-promotion-experiment-lab")
        dataset = os.environ.get("DBT_BIGQUERY_DATASET", "music_promotion_lab")
        if not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", project):
            raise ValueError("Invalid Google Cloud project ID.")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", dataset):
            raise ValueError("Invalid BigQuery dataset ID.")
        client = bigquery.Client(project=project)
        config = bigquery.QueryJobConfig(maximum_bytes_billed=1_000_000_000)
        query = f"select * from `{project}.{dataset}.fct_promotion_experiment`"
        return (
            client.query(query, job_config=config, location="US")
            .result()
            .to_dataframe(create_bqstorage_client=False)
        )
    if not database.exists():
        raise FileNotFoundError(f"dbt database not found at {database}")
    with duckdb.connect(str(database), read_only=True) as connection:
        return connection.execute("select * from analytics.fct_promotion_experiment").fetchdf()


def _analyze_segments(frame: pd.DataFrame, bootstrap_reps: int, seed: int) -> pd.DataFrame:
    rows = []
    for dimension_index, dimension in enumerate(SEGMENT_DIMENSIONS):
        for segment_index, segment in enumerate(sorted(frame[dimension].dropna().unique())):
            subset = frame.loc[frame[dimension].eq(segment)]
            if len(subset) < 200 or subset["assignment"].nunique() != 2:
                continue
            for metric_index, metric in enumerate(METRICS):
                result = clustered_rate_effect(
                    subset,
                    metric,
                    bootstrap_reps=bootstrap_reps,
                    seed=seed + dimension_index * 100 + segment_index * 10 + metric_index,
                )
                rows.append({"dimension": dimension, "segment": segment, **result})
    effects = pd.DataFrame(rows)
    effects["q_value"] = effects.groupby("metric", group_keys=False)["p_value"].apply(
        benjamini_hochberg
    )
    return effects


def _daily_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame["event_date"] = pd.to_datetime(frame["event_date"])
    frame["event_month"] = frame["event_date"].dt.to_period("M").astype(str)
    rows = []
    for (month, assignment), group in frame.groupby(["event_month", "assignment"]):
        rows.append(
            {
                "event_month": month,
                "assignment": assignment,
                "opportunities": len(group),
                "play_rate": group["played"].mean(),
                "qualified_listen_rate": group["qualified_listen"].mean(),
                "save_rate": group["saved"].mean(),
                "repeat_7d_rate": group["repeated_7d"].mean(),
                "skip_rate": group["skipped"].sum() / max(group["played"].sum(), 1),
            }
        )
    return pd.DataFrame(rows)


def analyze(database: Path, bootstrap_reps: int, seed: int, target: str = "local") -> dict:
    frame = _load_fact_table(database, target)
    metadata = json.loads(PROCESSED_METADATA_PATH.read_text(encoding="utf-8"))
    metadata["generated_at"] = datetime.now(UTC).isoformat()
    metadata["warehouse"] = target
    if len(frame) != metadata["experiment_rows"]:
        raise ValueError("Warehouse row count does not match this build's metadata.")

    summary = pd.DataFrame(
        [
            clustered_rate_effect(
                frame,
                metric,
                bootstrap_reps=bootstrap_reps,
                seed=seed + index,
            )
            for index, metric in enumerate(METRICS)
        ]
    )
    summary["q_value"] = benjamini_hochberg(summary["p_value"])
    segments = _analyze_segments(frame, bootstrap_reps=bootstrap_reps, seed=seed + 1000)
    srm = sample_ratio_mismatch(frame)
    primary = summary.loc[summary["metric"].eq("qualified_listen_rate")].iloc[0]
    power = minimum_detectable_effect(
        float(primary["control_rate"]), int(primary["n_control"]), int(primary["n_treatment"])
    )
    diversity = artist_diversity(frame)
    concentration = diversity_guardrail(frame, bootstrap_reps, seed + 2000)
    daily = _daily_metrics(frame)

    artifacts = PROJECT_ROOT / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    summary.to_csv(artifacts / "experiment_summary.csv", index=False)
    segments.to_csv(artifacts / "segment_effects.csv", index=False)
    pd.DataFrame([srm]).to_csv(artifacts / "srm_check.csv", index=False)
    pd.DataFrame([power]).to_csv(artifacts / "power_analysis.csv", index=False)
    diversity.to_csv(artifacts / "artist_diversity.csv", index=False)
    pd.DataFrame([concentration]).to_csv(artifacts / "diversity_guardrail.csv", index=False)
    daily.to_csv(artifacts / "monthly_metrics.csv", index=False)

    tableau = PROJECT_ROOT / "tableau"
    tableau.mkdir(parents=True, exist_ok=True)
    overall_for_tableau = summary.assign(dimension="overall", segment="all")
    metric_effects = pd.concat([overall_for_tableau, segments], ignore_index=True, sort=False)
    metric_effects.to_csv(tableau / "tableau_metric_effects.csv", index=False)
    daily.to_csv(tableau / "tableau_monthly_metrics.csv", index=False)
    extract_columns = [
        "experiment_id",
        "event_date",
        "assignment",
        "listener_segment",
        "track_age_segment",
        "artist_popularity_segment",
        "played",
        "qualified_listen",
        "saved",
        "skipped",
        "repeated_7d",
    ]
    frame[extract_columns].to_csv(tableau / "tableau_opportunities.csv", index=False)

    write_decision_memo(
        PROJECT_ROOT / "reports" / "decision_memo.md",
        summary,
        segments,
        srm,
        power,
        diversity,
        metadata,
        concentration,
    )
    write_dashboard_data(
        PROJECT_ROOT / "docs" / "data.js",
        summary,
        segments,
        srm,
        power,
        diversity,
        metadata,
        concentration,
    )
    analysis_metadata = {
        **metadata,
        "bootstrap_reps": bootstrap_reps,
        "srm_p_value": srm["p_value"],
        "primary_effect": float(primary["absolute_lift"]),
        "primary_ci": [float(primary["ci_lower"]), float(primary["ci_upper"])],
    }
    (artifacts / "analysis_metadata.json").write_text(
        json.dumps(analysis_metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(
        "Analysis complete: qualified-listen lift="
        f"{primary['absolute_lift'] * 100:+.2f} pp "
        f"(95% CI {primary['ci_lower'] * 100:+.2f} to {primary['ci_upper'] * 100:+.2f})."
    )
    return analysis_metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze the modeled promotion experiment.")
    parser.add_argument("--database", type=Path, default=DUCKDB_PATH)
    parser.add_argument("--bootstrap-reps", type=int, default=DEFAULT_BOOTSTRAP_REPS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--target", choices=["local", "bigquery"], default="local")
    args = parser.parse_args()
    analyze(args.database, bootstrap_reps=args.bootstrap_reps, seed=args.seed, target=args.target)


if __name__ == "__main__":
    main()
