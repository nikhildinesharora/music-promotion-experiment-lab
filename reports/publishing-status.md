# Publishing status

## Verified locally

- Last.fm source: 776,336 rows; 19,832 sampled opportunities from 50 listeners.
- Corrected past-only context features; deterministic simulated outcomes.
- Two dbt seeds, five models, and 38 dbt tests pass on DuckDB.
- Sixteen Python tests pass, including leakage, allocation, and decision failures.
- Browser checks cover four viewport sizes and all five metrics/three segments.
- Decision memo fits one printed Letter page.
- Tableau package: four worksheets and an embedded Hyper extract with aggregate
  results. Hyper contents, Document API parsing, and core schema validation pass. Tableau rendering and
  Public publication still need an interactive account session.

## BigQuery

Project: `music-promotion-experiment-lab`.
Dataset: `music_promotion_lab` in `US`.

Cloud execution completed: two seeds loaded, five models built, and all 38 dbt
tests passed in BigQuery. The final analysis was generated from its fact table
and reproduced the local +7.35 pp simulated primary effect (95% CI +5.83 to
+8.91 pp). The profile limits billed query bytes to 1 GB per query.

See `artifacts/warehouse_validation.json` for the independent warehouse parity
check and the cloud test invocation/results.

From the project directory in PowerShell:

```powershell
& .\scripts\connect_bigquery.ps1 -RunPipeline
```

Sign in using the Google account with access to this project. The script uses
the installed CLI or the prepared portable CLI in the temporary tools directory.
It then runs the same dbt contract in BigQuery and regenerates analysis from the
cloud fact table. Credentials stay in Google's normal local credential store.

## Tableau Public

Profile: https://public.tableau.com/app/profile/nikhil.arora1250

Open `tableau/Music-Promotion-Experiment-Lab.twbx` in Tableau Public, check
**Promotion Quality Review**, and save it to that profile. The profile URL alone
does not provide publishing access. Do not label the companion web dashboard
as Tableau or add an invented workbook URL.

After Tableau publishing, add the actual workbook URL to this status and the README.
