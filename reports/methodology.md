# Methodology

## Decision question

The experiment asks whether promotion creates qualified engagement rather than
only increasing the chance that a track starts playing. The primary metric is
therefore qualified-listen rate: the share of eligible opportunities that
produce a play without an early skip.

The analysis policy is implemented in `choose_recommendation`. It is a design
choice for this simulated case study, not a claim of preregistration:

1. SRM must pass at p >= 0.01.
2. The lower 95% bound for qualified-listen lift must exceed +1.0 pp.
3. The upper confidence bound for skip-rate degradation must not exceed +1.0
   percentage point.
4. The lower bound for seven-day repeat-rate change must be >= -0.5 pp.
5. The upper bound for relative artist-HHI increase must be <= 10%.
   Save rate is a secondary diagnostic.

A passing scenario is eligible for a live validation test; any failing criterion
holds the simulated rollout. Segments cannot override a failed guardrail.

## Data lineage

The real-data path downloads the 50-user development subset of the Last.fm 1K
dataset. Each row is a historical user-track timestamp. The builder:

1. Removes malformed/duplicate events and resolves simultaneous listener events
   deterministically to one context.
2. Resolves missing MusicBrainz identifiers with deterministic hashes of artist
   and track names.
3. Splits each listener history into sessions using a 30-minute inactivity gap.
4. Uses the first event in each session as an eligible promotion opportunity.
5. Derives prior artist and track activity, observed track tenure, artist
   reach, and whether the same track was heard in the preceding seven days.
6. Hashes source identifiers before writing dbt seeds.

"New" means the listener has no prior observation for that artist. "Returning"
means at least one prior artist listen. Track tenure is time since the track was
first observed in this dataset, not its release date. Artist popularity is based
on strictly earlier sample play counts: emerging <100, mid-tail 100-999,
established >=1000. These are sample-reach proxies, not industry popularity.
Simultaneous events share the same prior global count. A regression test appends
future events and checks that existing contexts do not change.

The first scrobbled track supplies a fixed candidate for a counterfactual replay.
It was already listened to; the opportunity pool therefore has selection bias.
When sampling, each listener contributes at most ceil(requested rows/listeners)
sessions; short histories can leave the output below the requested row count.

## Simulation contract

No public field is silently treated as campaign data. Assignment and outcomes
are generated in `src/music_promotion/simulation.py` with SHA-256-derived
uniform values and a fixed seed. The same inputs always produce the same trial.

The declared scenario gives promotion a larger play-rate effect for new
listeners, but a stronger save and repeat effect for returning listeners. New
listeners also have a simulated early-skip risk. This creates a useful product
tradeoff: broad reach may improve starts while affinity-based targeting creates
higher-quality engagement.

The simulated probability columns remain in the fact table so the data-
generating process can be audited. They would not exist in a real experiment.

## Statistical analysis

- Assignment is tested against a 50/50 allocation with a chi-square SRM check.
- Rate differences are treatment minus control in percentage points.
- Confidence intervals use a nonparametric listener-cluster bootstrap. A sampled
  listener brings all of their control and treatment opportunities into that
  bootstrap replicate.
- The default report uses 1,000 bootstrap replicates and a fixed seed.
- Segment p-values are adjusted with Benjamini-Hochberg within each metric
  family.
- MDE uses a two-sided 5% alpha, 80% power, the control primary-metric rate, and
  the smaller assignment arm. This is an IID Bernoulli planning approximation,
  ignores listener clustering, and uses an observed baseline. The output also
  reports the approximate per-arm size for a 2 pp effect. A live test requires
  a pilot and listener-level sizing, rather than treating this as achieved power.
- Artist concentration uses HHI and a paired listener-cluster bootstrap for its
  relative change. The unnormalized unique-artist count is descriptive and
  depends on sample size.
- P-values use the bootstrap standard error with a normal approximation; CIs
  are percentile bootstrap intervals. Small segment cluster counts are fragile.

## Threats to validity

- Fifty listeners are enough to exercise the pipeline, not to represent a
  streaming population.
- Historical Last.fm use differs from current on-demand streaming behavior.
- Session boundaries are inferred from inactivity.
- Session assignment assumes no carryover or interference. A live promotion
  test should randomize listeners and allow complete seven-day follow-up.
- Skip rate conditions on played tracks, which treatment changes. Interpret it
  as an operational guardrail, not an effect in a fixed causal subgroup.
- Post-exposure outcomes are simulated. The project demonstrates measurement
  and decision discipline, not external causal evidence.
- Segment findings are exploratory. A live follow-up must pre-register one
  targeting rule and preserve holdout traffic.

