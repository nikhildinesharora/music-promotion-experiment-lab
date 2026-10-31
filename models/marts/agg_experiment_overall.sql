with experiment as (
    select * from {{ ref('fct_promotion_experiment') }}
)

select
    assignment,
    count(*) as opportunities,
    sum(played) as plays,
    sum(qualified_listen) as qualified_listens,
    sum(saved) as saves,
    sum(skipped) as skips,
    sum(repeated_7d) as seven_day_repeats,
    avg(cast(played as {{ dbt.type_float() }})) as play_rate,
    avg(cast(qualified_listen as {{ dbt.type_float() }})) as qualified_listen_rate,
    avg(cast(saved as {{ dbt.type_float() }})) as save_rate,
    avg(cast(repeated_7d as {{ dbt.type_float() }})) as repeat_7d_rate,
    cast(sum(skipped) as {{ dbt.type_float() }}) / nullif(sum(played), 0) as skip_rate,
    count(distinct case when played = 1 then artist_id end) as played_unique_artists
from experiment
group by assignment

