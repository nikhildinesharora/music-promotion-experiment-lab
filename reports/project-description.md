# How to describe this project

## Short introduction

I built a music promotion experiment lab to ask whether a recommendation creates
qualified engagement or just another play. I used public Last.fm histories for
listener and track context, then explicitly simulated randomized promotion
outcomes because the public dataset has no campaign assignments, skips, or saves.

The project includes a BigQuery/dbt pipeline, data tests, listener-cluster
confidence intervals, allocation checks, power planning, exploratory segments,
and a product memo. Its key limitation is visible throughout: simulated results
validate the measurement workflow, not real business lift.

## Resume bullets

- Built a reproducible BigQuery/Python/SQL/dbt pipeline over 776K public listening events,
  creating 19.8K simulated promotion opportunities with metric contracts and
  38 warehouse validation checks.
- Implemented listener-cluster bootstrap intervals, sample-ratio checks,
  power/MDE planning, and adjusted segment comparisons; delivered an interactive
  readout, packaged Tableau workbook, and one-page product decision memo.

BigQuery execution is documented in `artifacts/warehouse_validation.json`.
Describe the Tableau workbook as published
only after an actual public workbook URL exists.

## Decisions worth discussing in an interview

- Qualified listens use all randomized opportunities as the denominator;
  measuring only plays would reward starts without measuring engagement.
- Repeated observations from the same listener are clustered in inference.
- Appending future data must not change historical feature values.
- An assignment failure or failed guardrail blocks the decision even when the
  primary lift looks attractive.
- Track tenure is not release age, and sample reach is not global popularity.
- A live experiment would require exposure instrumentation, listener-level
  assignment, and complete follow-up; this simulator assumes no carryover.
