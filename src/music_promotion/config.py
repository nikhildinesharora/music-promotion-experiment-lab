from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

SOURCE_URL = (
    "https://github.com/eifuentes/lastfm-dataset-1K/releases/download/"
    "v1.0/lastfm-dataset-50.snappy.parquet"
)
SOURCE_PATH = PROJECT_ROOT / "data" / "raw" / "lastfm-dataset-50.snappy.parquet"

CONTEXT_SEED_PATH = PROJECT_ROOT / "seeds" / "listening_contexts.csv"
OUTCOME_SEED_PATH = PROJECT_ROOT / "seeds" / "promotion_outcomes.csv"
PROCESSED_METADATA_PATH = PROJECT_ROOT / "data" / "processed" / "build_metadata.json"
DUCKDB_PATH = PROJECT_ROOT / "target" / "music_promotion.duckdb"

DEFAULT_SEED = 20261028
DEFAULT_ROWS = 30_000
DEFAULT_BOOTSTRAP_REPS = 1_000
SIMULATION_VERSION = "v2_past_only_context"
