# Music Promotion Experiment Lab: decision memo

**Scenario qualifies for a live validation test**

Simulated campaign outcomes over 19,832 session opportunities from 50 listeners. Historical Last.fm listening supplies context; no real promotion ran.

| Metric | Control | Treatment | Change | 95% CI |
| --- | ---: | ---: | ---: | --- |
| Qualified listen rate | 45.6% | 52.9% | +7.3 pp | +5.8 to +8.9 pp |
| Play rate | 59.5% | 68.7% | +9.2 pp | +7.7 to +10.8 pp |
| Save rate | 5.3% | 7.4% | +2.1 pp | +1.4 to +2.8 pp |
| Seven-day repeat rate | 8.4% | 10.5% | +2.1 pp | +1.2 to +3.0 pp |
| Skip rate | 23.4% | 22.9% | -0.5 pp | -1.8 to +1.0 pp |

## Interpretation

The generated scenario changes qualified listening by +7.3 percentage points. This answers the measurement question within the simulator. It is not evidence of commercial lift. Qualified listening improves by more than 1 pp at the lower confidence bound; skip, repeat-listening, and artist-diversity checks pass.

SRM p=0.865 (9,928 control / 9,904 treatment). Artist HHI changes -7.0%, with a 95% interval of -15.2% to +1.8%; the allowed relative increase is 10%. Confidence intervals resample listeners.

## Next decision

Before a live test, log eligible exposures, playback/skip timing, saves, and complete seven-day follow-up. Randomize by listener to avoid cross-session carryover. Pre-register qualified listening and guardrail tolerances; use a separate pilot to estimate listener-level variance and size the test. The IID approximation here is 2.0 pp at 80% power; it ignores clustering and is not a live-test sample-size commitment.

## Limits

The candidate tracks were already scrobbled, so the opportunity pool is selected. Track age is observed tenure, not release age; artist popularity is prior sample reach. Only 50 historical listeners support the real-context analysis. Segments are exploratory with BH-adjusted p-values, not evidence that one segment beats another. Simulated outcomes assume no carryover or interference.
