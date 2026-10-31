with source as (
    select * from {{ ref('promotion_outcomes') }}
)

select
    cast(experiment_id as {{ dbt.type_string() }}) as experiment_id,
    cast(assignment as {{ dbt.type_string() }}) as assignment,
    cast(played as integer) as played,
    cast(qualified_listen as integer) as qualified_listen,
    cast(skipped as integer) as skipped,
    cast(saved as integer) as saved,
    cast(repeated_7d as integer) as repeated_7d,
    cast(sim_p_play as {{ dbt.type_float() }}) as sim_p_play,
    cast(sim_p_skip_given_play as {{ dbt.type_float() }}) as sim_p_skip_given_play,
    cast(sim_p_save_given_play as {{ dbt.type_float() }}) as sim_p_save_given_play,
    cast(sim_p_repeat_given_play as {{ dbt.type_float() }}) as sim_p_repeat_given_play,
    cast(simulation_version as {{ dbt.type_string() }}) as simulation_version
from source

