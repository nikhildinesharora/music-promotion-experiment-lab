with balance as (
    select
        avg(case when assignment = 'treatment' then 1.0 else 0.0 end) as treatment_share
    from {{ ref('fct_promotion_experiment') }}
)

select *
from balance
where abs(treatment_share - 0.5) > 0.03

