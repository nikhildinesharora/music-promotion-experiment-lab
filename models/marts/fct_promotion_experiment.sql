with contexts as (
    select * from {{ ref('stg_listening_contexts') }}
),

outcomes as (
    select * from {{ ref('stg_promotion_outcomes') }}
)

select
    contexts.experiment_id,
    contexts.listener_id,
    contexts.session_id,
    contexts.event_timestamp,
    contexts.event_date,
    contexts.track_id,
    contexts.artist_id,
    contexts.listener_segment,
    contexts.track_age_segment,
    contexts.artist_popularity_segment,
    contexts.baseline_repeat_7d,
    contexts.prior_artist_plays,
    contexts.prior_track_plays,
    contexts.listener_prior_plays,
    contexts.artist_prior_global_plays,
    contexts.source_mode,
    outcomes.assignment,
    outcomes.played,
    outcomes.qualified_listen,
    outcomes.skipped,
    outcomes.saved,
    outcomes.repeated_7d,
    outcomes.sim_p_play,
    outcomes.sim_p_skip_given_play,
    outcomes.sim_p_save_given_play,
    outcomes.sim_p_repeat_given_play,
    outcomes.simulation_version
from contexts
inner join outcomes using (experiment_id)

