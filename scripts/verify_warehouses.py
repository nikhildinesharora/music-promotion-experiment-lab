"""Check that BigQuery and DuckDB contain the same modeled trial."""

import hashlib
import json
from datetime import UTC, datetime

from analyze_experiment import PROJECT_ROOT, _load_fact_table


def digest(frame):
    columns = [
        "experiment_id",
        "assignment",
        "listener_segment",
        "track_age_segment",
        "artist_popularity_segment",
        "played",
        "qualified_listen",
        "skipped",
        "saved",
        "repeated_7d",
    ]
    canonical = frame[columns].sort_values("experiment_id").to_csv(index=False, lineterminator="\n")
    return hashlib.sha256(canonical.encode()).hexdigest()


def main():
    local = _load_fact_table(PROJECT_ROOT / "target/music_promotion.duckdb")
    cloud = _load_fact_table(PROJECT_ROOT / "target/music_promotion.duckdb", "bigquery")
    local_hash, cloud_hash = digest(local), digest(cloud)
    assert len(local) == len(cloud), "Warehouse row counts differ"
    assert local_hash == cloud_hash, "Warehouse assignment, segment, or outcome values differ"
    results = json.loads((PROJECT_ROOT / "target/run_results.json").read_text())
    tests = [
        {
            "name": row["unique_id"],
            "status": row["status"],
            "execution_seconds": row["execution_time"],
        }
        for row in results["results"]
    ]
    assert tests and all(row["status"] == "pass" for row in tests)
    evidence = {
        "verified_at": datetime.now(UTC).isoformat(),
        "project": "music-promotion-experiment-lab",
        "dataset": "music_promotion_lab",
        "rows_per_warehouse": len(local),
        "matched_sha256": local_hash,
        "compared_fields": "assignment, segments, and five outcomes, keyed by opportunity",
        "dbt_invocation_id": results["metadata"]["invocation_id"],
        "cloud_tests": tests,
    }
    (PROJECT_ROOT / "artifacts/warehouse_validation.json").write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
    )
    print(f"PASS: {len(local):,} rows match across warehouses; {len(tests)} cloud tests pass.")


if __name__ == "__main__":
    main()
