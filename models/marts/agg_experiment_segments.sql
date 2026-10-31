with experiment as (
    select * from {{ ref('fct_promotion_experiment') }}
),

long_segments as (
    select
        assignment,
        'listener_segment' as dimension,
        listener_segment as segment,
        played,
        qualified_listen,
        saved,
        skipped,
        repeated_7d
    from experiment

    union all

    select
        assignment,
        'track_age_segment' as dimension,
        track_age_segment as segment,
        played,
        qualified_listen,
        saved,
        skipped,
        repeated_7d
    from experiment

    union all

    select
        assignment,
        'artist_popularity_segment' as dimension,
        artist_popularity_segment as segment,
        played,
        qualified_listen,
        saved,
        skipped,
        repeated_7d
    from experiment
)

select
    dimension,
    segment,
    assignment,
    count(*) as opportunities,
    avg(cast(played as {{ dbt.type_float() }})) as play_rate,
    avg(cast(qualified_listen as {{ dbt.type_float() }})) as qualified_listen_rate,
    avg(cast(saved as {{ dbt.type_float() }})) as save_rate,
    avg(cast(repeated_7d as {{ dbt.type_float() }})) as repeat_7d_rate,
    cast(sum(skipped) as {{ dbt.type_float() }}) / nullif(sum(played), 0) as skip_rate
from long_segments
group by dimension, segment, assignment

