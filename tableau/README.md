# Tableau Public dashboard

Open `Music-Promotion-Experiment-Lab.twbx` in Tableau Public. It contains an
embedded Hyper extract and a dashboard named **Promotion Quality Review** with
four worksheets: rates, overall intervals, exploratory segment intervals, and
experiment health. All data in the package is aggregated; no listener IDs or
listening histories are included.

The repaired package was opened in Tableau Public 2026.3, and its embedded data
rendered in the Rates worksheet. The Hyper rows and package consistency are also
checked programmatically. Public publication still requires an interactive
Tableau session; no public workbook URL is claimed yet.

The generator uses Tableau's `18.1` serialization format with explicit feature
declarations. It intentionally avoids the `ManifestByVersion` shortcut, which
caused additional grammar errors in the installed 2026.3 application. XSD checks
alone are not treated as proof that Tableau can open a workbook.

Rebuild from the latest statistical outputs:

```bash
pip install -r requirements-tableau.txt
python scripts/build_tableau.py
```

Target profile: https://public.tableau.com/app/profile/nikhil.arora1250

The analysis also produces three clean CSV extracts:

- `tableau_metric_effects.csv`: overall and segmented treatment effects with
  confidence intervals and adjusted p-values.
- `tableau_monthly_metrics.csv`: arm-level metric trends by observed month.
- `tableau_opportunities.csv`: one row per experiment opportunity for drilldown.

## Workbook structure

The generated dashboard is 1,280 x 1,100. The following guide supports further
editing in Tableau, including adding a metric filter to the segment view.

### 1. Decision scorecard

Use `tableau_metric_effects.csv`, filter `dimension = overall`, and display:

- Qualified listen absolute lift
- 95% confidence interval
- Play-rate lift
- Skip-rate lift
- IID planning MDE (ignores listener clustering)

Use percentage-point units, not relative percent, for the primary decision.

### 2. Control versus treatment

Create side-by-side bars using `metric_label` on rows and Measure Values for
`control_rate` and `treatment_rate`. Keep only the overall rows. Format rates as
percentages with one decimal place.

### 3. Segment effect plot

Use `dimension` and `segment` on rows. Plot `absolute_lift` as a circle and use
`ci_lower` and `ci_upper` for the confidence interval. Add a zero reference
line. Color points by this calculated field:

```text
IF [ci_lower] > 0 THEN "Positive"
ELSEIF [ci_upper] < 0 THEN "Negative"
ELSE "Uncertain"
END
```

Add `metric_label` as a single-value dashboard filter. Display `q_value` in the
tooltip and label all segment cuts as exploratory.

### 4. Experiment health

Use a text table for assignment counts, treatment share, SRM p-value, listener
clusters, source mode, and simulation version. Place the simulation disclaimer
directly beneath the dashboard title.

## Publish checklist

1. Refresh all extracts by running the pipeline.
2. Confirm the dashboard says **simulated campaign outcomes** in the first
   viewport.
3. Verify percentage points are not formatted as relative percentages.
4. Verify all filters preserve an explicit control comparison.
5. Sign in to the profile above, publish to Tableau Public, and add the actual workbook URL to the project
   README and portfolio.

Tableau publication requires an interactive Tableau Public account and is not
automated by this repository. The companion dashboard in `docs/` presents the
same outputs and can be published with GitHub Pages immediately.

