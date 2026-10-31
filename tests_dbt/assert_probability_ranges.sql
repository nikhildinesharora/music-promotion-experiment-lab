select *
from {{ ref('fct_promotion_experiment') }}
where sim_p_play not between 0 and 1
   or sim_p_skip_given_play not between 0 and 1
   or sim_p_save_given_play not between 0 and 1
   or sim_p_repeat_given_play not between 0 and 1

