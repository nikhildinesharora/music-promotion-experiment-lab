select *
from {{ ref('fct_promotion_experiment') }}
where (listener_segment = 'new' and prior_artist_plays <> 0)
   or (listener_segment = 'returning' and prior_artist_plays <= 0)
   or prior_track_plays > prior_artist_plays
   or prior_artist_plays > listener_prior_plays
   or (baseline_repeat_7d = 1 and prior_track_plays = 0)
   or (artist_popularity_segment = 'established' and artist_prior_global_plays < 1000)
   or (artist_popularity_segment = 'mid_tail' and
       (artist_prior_global_plays < 100 or artist_prior_global_plays >= 1000))
   or (artist_popularity_segment = 'emerging' and artist_prior_global_plays >= 100)

