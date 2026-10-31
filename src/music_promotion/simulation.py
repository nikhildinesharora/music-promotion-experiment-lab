from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

CONTEXT_COLUMNS = [
    "experiment_id",
    "listener_id",
    "session_id",
    "event_timestamp",
    "event_date",
    "track_id",
    "artist_id",
    "listener_segment",
    "track_age_segment",
    "artist_popularity_segment",
    "baseline_repeat_7d",
    "prior_artist_plays",
    "prior_track_plays",
    "listener_prior_plays",
    "artist_prior_global_plays",
    "source_mode",
]


@dataclass(frozen=True)
class BuildSummary:
    source_rows: int
    eligible_sessions: int
    experiment_rows: int
    listeners: int
    tracks: int
    artists: int


def stable_id(value: object, prefix: str) -> str:
    digest = hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def stable_uniform(seed: int, key: object, stream: str) -> float:
    payload = f"{seed}|{key}|{stream}".encode()
    integer = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
    return (integer + 0.5) / (2**64)


def _identity_key(identifier: pd.Series, name: pd.Series, prefix: str) -> pd.Series:
    clean_id = identifier.fillna("").astype(str).str.strip()
    clean_name = name.fillna("unknown").astype(str).str.strip().str.lower()
    raw = clean_id.where(clean_id.ne(""), clean_name)
    return raw.map(lambda value: stable_id(value, prefix))


def _balanced_sample(frame: pd.DataFrame, n_rows: int, seed: int) -> pd.DataFrame:
    if len(frame) <= n_rows:
        return frame.copy()

    listeners = max(frame["listener_id_raw"].nunique(), 1)
    per_listener = math.ceil(n_rows / listeners)
    sampled_parts = []
    for _, group in frame.groupby("listener_id_raw", sort=True):
        take = min(len(group), per_listener)
        sampled_parts.append(group.sample(n=take, random_state=seed))

    sampled = pd.concat(sampled_parts, ignore_index=True)
    if len(sampled) > n_rows:
        sampled = sampled.sample(n=n_rows, random_state=seed)
    return sampled.sort_values(["listener_id_raw", "event_timestamp"]).reset_index(drop=True)


def build_contexts_from_lastfm(
    events: pd.DataFrame, n_rows: int, seed: int
) -> tuple[pd.DataFrame, BuildSummary]:
    if n_rows < 1:
        raise ValueError("n_rows must be positive.")
    required = {
        "user_id",
        "timestamp",
        "artist_id",
        "artist_name",
        "track_id",
        "track_name",
    }
    missing = required.difference(events.columns)
    if missing:
        raise ValueError(f"Source data is missing columns: {sorted(missing)}")

    data = events[list(required)].copy()
    source_rows = len(data)
    data["event_timestamp"] = pd.to_datetime(data["timestamp"], utc=True, errors="coerce")
    data = data.dropna(subset=["user_id", "event_timestamp"])
    data["artist_key"] = _identity_key(data["artist_id"], data["artist_name"], "artist")
    data["track_key"] = _identity_key(
        data["track_id"],
        data["artist_name"].fillna("") + "|" + data["track_name"].fillna(""),
        "track",
    )
    data = data.drop_duplicates(subset=["user_id", "event_timestamp", "track_key"])
    data = data.sort_values(["user_id", "event_timestamp", "track_key"])
    # A listener cannot supply two distinct exposure contexts at the same instant.
    data = data.drop_duplicates(["user_id", "event_timestamp"]).reset_index(drop=True)
    if data.empty:
        raise ValueError("No usable listening events remain after cleaning.")

    data["listener_prior_plays"] = data.groupby("user_id").cumcount()
    data["prior_artist_plays"] = data.groupby(["user_id", "artist_key"]).cumcount()
    data["prior_track_plays"] = data.groupby(["user_id", "track_key"]).cumcount()

    previous_track_time = data.groupby(["user_id", "track_key"])["event_timestamp"].shift(1)
    data["baseline_repeat_7d"] = (
        previous_track_time.notna()
        & ((data["event_timestamp"] - previous_track_time) <= pd.Timedelta(days=7))
    ).astype(int)

    first_track_seen = data.groupby("track_key")["event_timestamp"].transform("min")
    data["track_age_days"] = (
        (data["event_timestamp"] - first_track_seen).dt.total_seconds() / 86_400
    ).clip(lower=0)

    # Count strictly earlier plays; simultaneous events share the same prior count.
    artist_counts = data.groupby(["artist_key", "event_timestamp"], sort=True).size()
    prior_counts = artist_counts.groupby(level=0).cumsum() - artist_counts
    data["artist_prior_global_plays"] = prior_counts.reindex(
        pd.MultiIndex.from_frame(data[["artist_key", "event_timestamp"]])
    ).to_numpy()

    gap = data.groupby("user_id")["event_timestamp"].diff()
    session_start = gap.isna() | (gap > pd.Timedelta(minutes=30))
    data["session_number"] = session_start.groupby(data["user_id"]).cumsum().astype(int)

    opportunities = data.loc[session_start].copy()
    eligible_sessions = len(opportunities)
    opportunities["listener_id_raw"] = opportunities["user_id"].astype(str)
    opportunities = _balanced_sample(opportunities, n_rows=n_rows, seed=seed)

    opportunities["listener_id"] = opportunities["listener_id_raw"].map(
        lambda value: stable_id(value, "listener")
    )
    opportunities["session_id"] = opportunities.apply(
        lambda row: stable_id(
            f"{row['listener_id_raw']}|{row['session_number']}|{row['event_timestamp'].isoformat()}",
            "session",
        ),
        axis=1,
    )
    opportunities["experiment_id"] = opportunities["session_id"].str.replace(
        "session_", "exp_", regex=False
    )
    opportunities["track_id"] = opportunities["track_key"]
    opportunities["artist_id"] = opportunities["artist_key"]
    opportunities["event_date"] = opportunities["event_timestamp"].dt.date.astype(str)
    opportunities["event_timestamp"] = opportunities["event_timestamp"].dt.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    opportunities["listener_segment"] = np.where(
        opportunities["prior_artist_plays"].gt(0), "returning", "new"
    )
    opportunities["track_age_segment"] = pd.cut(
        opportunities["track_age_days"],
        bins=[-1, 30, 180, float("inf")],
        labels=["0-30_days", "31-180_days", "181+_days"],
    ).astype(str)
    opportunities["artist_popularity_segment"] = np.select(
        [
            opportunities["artist_prior_global_plays"].ge(1000),
            opportunities["artist_prior_global_plays"].ge(100),
        ],
        ["established", "mid_tail"],
        default="emerging",
    )
    opportunities["source_mode"] = "lastfm_real_context"

    contexts = opportunities[CONTEXT_COLUMNS].copy()
    contexts[
        [
            "baseline_repeat_7d",
            "prior_artist_plays",
            "prior_track_plays",
            "listener_prior_plays",
            "artist_prior_global_plays",
        ]
    ] = contexts[
        [
            "baseline_repeat_7d",
            "prior_artist_plays",
            "prior_track_plays",
            "listener_prior_plays",
            "artist_prior_global_plays",
        ]
    ].astype(int)

    summary = BuildSummary(
        source_rows=source_rows,
        eligible_sessions=eligible_sessions,
        experiment_rows=len(contexts),
        listeners=contexts["listener_id"].nunique(),
        tracks=contexts["track_id"].nunique(),
        artists=contexts["artist_id"].nunique(),
    )
    return contexts, summary


def build_demo_contexts(n_rows: int, seed: int) -> tuple[pd.DataFrame, BuildSummary]:
    if n_rows < 1:
        raise ValueError("n_rows must be positive.")
    rng = np.random.default_rng(seed)
    listeners = max(80, min(400, n_rows // 15))
    listener_ids = [stable_id(f"demo-{index}", "listener") for index in range(listeners)]
    track_ids = [stable_id(f"track-{index}", "track") for index in range(max(300, n_rows // 5))]
    artist_ids = [stable_id(f"artist-{index}", "artist") for index in range(max(100, n_rows // 20))]
    dates = pd.Timestamp("2026-01-01", tz="UTC") + pd.to_timedelta(
        rng.integers(0, 120, size=n_rows), unit="D"
    )
    contexts = pd.DataFrame(
        {
            "experiment_id": [stable_id(f"demo-exp-{index}", "exp") for index in range(n_rows)],
            "listener_id": rng.choice(listener_ids, size=n_rows),
            "session_id": [
                stable_id(f"demo-session-{index}", "session") for index in range(n_rows)
            ],
            "event_timestamp": dates.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "event_date": dates.strftime("%Y-%m-%d"),
            "track_id": rng.choice(track_ids, size=n_rows),
            "artist_id": rng.choice(artist_ids, size=n_rows),
            "listener_segment": rng.choice(["new", "returning"], p=[0.58, 0.42], size=n_rows),
            "track_age_segment": rng.choice(
                ["0-30_days", "31-180_days", "181+_days"], p=[0.35, 0.40, 0.25], size=n_rows
            ),
            "artist_popularity_segment": rng.choice(
                ["emerging", "mid_tail", "established"], p=[0.50, 0.30, 0.20], size=n_rows
            ),
            "baseline_repeat_7d": rng.binomial(1, 0.16, size=n_rows),
            "prior_artist_plays": rng.poisson(2.4, size=n_rows),
            "prior_track_plays": rng.poisson(0.8, size=n_rows),
            "listener_prior_plays": rng.integers(0, 5000, size=n_rows),
            "artist_prior_global_plays": rng.integers(0, 3000, size=n_rows),
            "source_mode": "synthetic_ci_fixture",
        }
    )
    contexts.loc[contexts["listener_segment"].eq("new"), "prior_artist_plays"] = 0
    contexts.loc[contexts["listener_segment"].eq("returning"), "prior_artist_plays"] += 1
    contexts["prior_track_plays"] = np.minimum(
        contexts["prior_track_plays"], contexts["prior_artist_plays"]
    )
    contexts.loc[contexts["prior_track_plays"].eq(0), "baseline_repeat_7d"] = 0
    contexts["listener_prior_plays"] = np.maximum(
        contexts["listener_prior_plays"], contexts["prior_artist_plays"]
    )
    contexts["artist_popularity_segment"] = np.select(
        [
            contexts["artist_prior_global_plays"].ge(1000),
            contexts["artist_prior_global_plays"].ge(100),
        ],
        ["established", "mid_tail"],
        default="emerging",
    )
    summary = BuildSummary(
        source_rows=n_rows,
        eligible_sessions=n_rows,
        experiment_rows=n_rows,
        listeners=contexts["listener_id"].nunique(),
        tracks=contexts["track_id"].nunique(),
        artists=contexts["artist_id"].nunique(),
    )
    return contexts[CONTEXT_COLUMNS], summary


def simulate_campaign(contexts: pd.DataFrame, seed: int, version: str) -> pd.DataFrame:
    returning = contexts["listener_segment"].eq("returning").astype(float)
    new_listener = 1.0 - returning
    recent_track = contexts["track_age_segment"].eq("0-30_days").astype(float)
    emerging_artist = contexts["artist_popularity_segment"].eq("emerging").astype(float)
    baseline_repeat = contexts["baseline_repeat_7d"].astype(float)

    treatment = np.array(
        [stable_uniform(seed, key, "assignment") < 0.5 for key in contexts["experiment_id"]],
        dtype=int,
    )

    p_play_control = np.clip(
        0.50
        + 0.08 * returning
        + 0.05 * baseline_repeat
        + 0.02 * recent_track
        - 0.01 * emerging_artist,
        0.05,
        0.92,
    )
    play_lift = 0.13 * new_listener + 0.09 * returning
    p_play = np.clip(p_play_control + treatment * play_lift, 0.01, 0.98)

    p_skip_control = np.clip(
        0.23 + 0.07 * new_listener + 0.015 * emerging_artist - 0.025 * baseline_repeat,
        0.02,
        0.80,
    )
    skip_lift = 0.035 * new_listener - 0.012 * returning
    p_skip = np.clip(p_skip_control + treatment * skip_lift, 0.01, 0.90)

    p_save_control = np.clip(
        0.035 + 0.045 * returning + 0.030 * baseline_repeat + 0.010 * recent_track,
        0.005,
        0.50,
    )
    save_lift = 0.002 * new_listener + 0.022 * returning + 0.006 * recent_track
    p_save = np.clip(p_save_control + treatment * save_lift, 0.001, 0.70)

    p_repeat_control = np.clip(
        0.055 + 0.100 * baseline_repeat + 0.045 * returning + 0.005 * recent_track,
        0.005,
        0.65,
    )
    repeat_lift = 0.001 * new_listener + 0.020 * returning + 0.006 * recent_track
    p_repeat = np.clip(p_repeat_control + treatment * repeat_lift, 0.001, 0.75)

    keys = contexts["experiment_id"].tolist()
    u_play = np.array([stable_uniform(seed, key, "played") for key in keys])
    u_skip = np.array([stable_uniform(seed, key, "skipped") for key in keys])
    u_save = np.array([stable_uniform(seed, key, "saved") for key in keys])
    u_repeat = np.array([stable_uniform(seed, key, "repeat") for key in keys])

    played = (u_play < p_play).astype(int)
    skipped = (played & (u_skip < p_skip)).astype(int)
    saved = (played & (u_save < p_save)).astype(int)
    repeated = (played & (u_repeat < p_repeat)).astype(int)
    qualified = (played & (1 - skipped)).astype(int)

    return pd.DataFrame(
        {
            "experiment_id": contexts["experiment_id"],
            "assignment": np.where(treatment == 1, "treatment", "control"),
            "played": played,
            "qualified_listen": qualified,
            "skipped": skipped,
            "saved": saved,
            "repeated_7d": repeated,
            "sim_p_play": p_play.round(6),
            "sim_p_skip_given_play": p_skip.round(6),
            "sim_p_save_given_play": p_save.round(6),
            "sim_p_repeat_given_play": p_repeat.round(6),
            "simulation_version": version,
        }
    )
