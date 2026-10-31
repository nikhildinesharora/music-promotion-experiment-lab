import pandas as pd

from music_promotion.simulation import (
    build_contexts_from_lastfm,
    build_demo_contexts,
    simulate_campaign,
)


def test_campaign_is_deterministic_and_consistent():
    contexts, _ = build_demo_contexts(n_rows=2_000, seed=17)
    first = simulate_campaign(contexts, seed=17, version="test")
    second = simulate_campaign(contexts, seed=17, version="test")

    pd.testing.assert_frame_equal(first, second)
    assert 0.46 < first["assignment"].eq("treatment").mean() < 0.54
    assert (first["qualified_listen"] <= first["played"]).all()
    assert (first["skipped"] <= first["played"]).all()
    assert (first["saved"] <= first["played"]).all()
    assert (first["repeated_7d"] <= first["played"]).all()


def test_real_context_builder_uses_session_boundaries_and_history():
    events = pd.DataFrame(
        [
            ["u1", "2026-01-01T10:00:00Z", "a1", "Artist 1", "t1", "Track 1"],
            ["u1", "2026-01-01T10:05:00Z", "a1", "Artist 1", "t2", "Track 2"],
            ["u1", "2026-01-02T10:00:00Z", "a1", "Artist 1", "t1", "Track 1"],
            ["u2", "2026-01-01T11:00:00Z", "a2", "Artist 2", "t3", "Track 3"],
            ["u2", "2026-01-01T12:00:00Z", "a2", "Artist 2", "t4", "Track 4"],
        ],
        columns=["user_id", "timestamp", "artist_id", "artist_name", "track_id", "track_name"],
    )
    contexts, summary = build_contexts_from_lastfm(events, n_rows=20, seed=3)

    assert summary.eligible_sessions == 4
    assert contexts["experiment_id"].is_unique
    assert set(contexts["listener_segment"]) == {"new", "returning"}
    assert contexts.loc[contexts["listener_segment"].eq("new"), "prior_artist_plays"].eq(0).all()
    first = contexts.loc[contexts["event_timestamp"].eq("2026-01-01T10:00:00Z")].iloc[0]
    later = contexts.loc[contexts["event_timestamp"].eq("2026-01-02T10:00:00Z")].iloc[0]
    assert first.baseline_repeat_7d == 0
    assert later.baseline_repeat_7d == 1


def test_future_events_cannot_change_existing_context_features():
    columns = ["user_id", "timestamp", "artist_id", "artist_name", "track_id", "track_name"]
    history = pd.DataFrame(
        [
            ["u1", "2026-01-01T10:00:00Z", "a1", "Artist", "t1", "Track"],
            ["u1", "2026-01-02T10:00:00Z", "a1", "Artist", "t1", "Track"],
            ["u2", "2026-01-02T10:00:00Z", "a1", "Artist", "t1", "Track"],
        ],
        columns=columns,
    )
    future = pd.DataFrame(
        [
            ["u1", time.isoformat(), "a1", "Artist", "t1", "Track"]
            for time in pd.date_range("2026-02-01", periods=1100, freq="h", tz="UTC")
        ],
        columns=columns,
    )
    before, _ = build_contexts_from_lastfm(history, n_rows=2000, seed=3)
    after, _ = build_contexts_from_lastfm(pd.concat([history, future]), n_rows=2000, seed=3)
    retained = after.set_index("experiment_id").loc[before.experiment_id].reset_index()
    pd.testing.assert_frame_equal(before.reset_index(drop=True), retained)
    simultaneous = before.loc[before.event_timestamp.eq("2026-01-02T10:00:00Z")]
    assert simultaneous.artist_prior_global_plays.eq(1).all()


def test_demo_history_is_internally_consistent():
    frame, _ = build_demo_contexts(4000, seed=19)
    assert (frame.prior_track_plays <= frame.prior_artist_plays).all()
    assert (frame.prior_artist_plays <= frame.listener_prior_plays).all()
    assert frame.loc[frame.listener_segment.eq("returning"), "prior_artist_plays"].gt(0).all()
    assert frame.loc[frame.baseline_repeat_7d.eq(1), "prior_track_plays"].gt(0).all()
