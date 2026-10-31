select *
from {{ ref('fct_promotion_experiment') }}
where qualified_listen > played
   or skipped > played
   or saved > played
   or repeated_7d > played
   or qualified_listen + skipped > played

