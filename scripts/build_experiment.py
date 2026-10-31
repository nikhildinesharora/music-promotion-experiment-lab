from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from music_promotion.config import (  # noqa: E402
    CONTEXT_SEED_PATH,
    DEFAULT_ROWS,
    DEFAULT_SEED,
    OUTCOME_SEED_PATH,
    PROCESSED_METADATA_PATH,
    SIMULATION_VERSION,
    SOURCE_PATH,
)
from music_promotion.simulation import (  # noqa: E402
    build_contexts_from_lastfm,
    build_demo_contexts,
    simulate_campaign,
)


def build_experiment(
    *,
    source_path: Path = SOURCE_PATH,
    n_rows: int = DEFAULT_ROWS,
    seed: int = DEFAULT_SEED,
    demo: bool = False,
) -> dict:
    if demo:
        contexts, summary = build_demo_contexts(n_rows=n_rows, seed=seed)
    else:
        if not source_path.exists():
            raise FileNotFoundError(
                f"Source data not found at {source_path}. Run scripts/download_lastfm.py first."
            )
        events = pd.read_parquet(source_path)
        contexts, summary = build_contexts_from_lastfm(events, n_rows=n_rows, seed=seed)

    outcomes = simulate_campaign(contexts, seed=seed, version=SIMULATION_VERSION)
    if not contexts["experiment_id"].is_unique:
        raise ValueError("Context builder produced duplicate experiment IDs.")
    if not outcomes["experiment_id"].is_unique:
        raise ValueError("Simulation produced duplicate experiment IDs.")
    if set(contexts["experiment_id"]) != set(outcomes["experiment_id"]):
        raise ValueError("Context and outcome experiment IDs do not match.")

    CONTEXT_SEED_PATH.parent.mkdir(parents=True, exist_ok=True)
    contexts.to_csv(CONTEXT_SEED_PATH, index=False, lineterminator="\n")
    outcomes.to_csv(OUTCOME_SEED_PATH, index=False, lineterminator="\n")

    metadata = {
        **asdict(summary),
        "generated_at": datetime.now(UTC).isoformat(),
        "seed": seed,
        "source_mode": contexts["source_mode"].iloc[0],
        "simulation_version": SIMULATION_VERSION,
        "treatment_share": float(outcomes["assignment"].eq("treatment").mean()),
        "context_seed": str(CONTEXT_SEED_PATH.relative_to(PROJECT_ROOT)),
        "outcome_seed": str(OUTCOME_SEED_PATH.relative_to(PROJECT_ROOT)),
    }
    PROCESSED_METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROCESSED_METADATA_PATH.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(
        f"Built {len(contexts):,} experiment opportunities from "
        f"{summary.listeners:,} listeners; treatment share={metadata['treatment_share']:.3f}."
    )
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Build listening contexts and simulated outcomes.")
    parser.add_argument("--source", type=Path, default=SOURCE_PATH)
    parser.add_argument("--rows", type=int, default=DEFAULT_ROWS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--demo", action="store_true", help="Use a synthetic CI fixture.")
    args = parser.parse_args()
    build_experiment(source_path=args.source, n_rows=args.rows, seed=args.seed, demo=args.demo)


if __name__ == "__main__":
    main()
