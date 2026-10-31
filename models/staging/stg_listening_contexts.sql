with source as (
    select * from {{ ref('listening_contexts') }}
)

select
    cast(experiment_id as {{ dbt.type_string() }}) as experiment_id,
    cast(listener_id as {{ dbt.type_string() }}) as listener_id,
    cast(session_id as {{ dbt.type_string() }}) as session_id,
    cast(event_timestamp as timestamp) as event_timestamp,
    cast(event_date as date) as event_date,
    cast(track_id as {{ dbt.type_string() }}) as track_id,
    cast(artist_id as {{ dbt.type_string() }}) as artist_id,
    cast(listener_segment as {{ dbt.type_string() }}) as listener_segment,
    cast(track_age_segment as {{ dbt.type_string() }}) as track_age_segment,
    cast(artist_popularity_segment as {{ dbt.type_string() }}) as artist_popularity_segment,
    cast(baseline_repeat_7d as integer) as baseline_repeat_7d,
    cast(prior_artist_plays as integer) as prior_artist_plays,
    cast(prior_track_plays as integer) as prior_track_plays,
    cast(listener_prior_plays as integer) as listener_prior_plays,
    cast(artist_prior_global_plays as integer) as artist_prior_global_plays,
    cast(source_mode as {{ dbt.type_string() }}) as source_mode
from source

