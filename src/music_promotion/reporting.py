from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd


def _metric_row(summary: pd.DataFrame, metric: str) -> pd.Series:
    return summary.loc[summary["metric"].eq(metric)].iloc[0]


def _percent(value: float, decimals: int = 1) -> str:
    return f"{value * 100:.{decimals}f}%"


def _pp(value: float, decimals: int = 1) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value * 100:.{decimals}f} pp"


def choose_recommendation(summary: pd.DataFrame, srm: dict, concentration: dict) -> tuple[str, str]:
    primary = _metric_row(summary, "qualified_listen_rate")
    skip = _metric_row(summary, "skip_rate")
    repeat = _metric_row(summary, "repeat_7d_rate")
    if not srm["passes_at_0_01"]:
        return "Investigate assignment before interpreting lift", "The sample-ratio check failed."

    if (
        primary["ci_lower"] > 0.01
        and skip["ci_upper"] <= 0.01
        and repeat["ci_lower"] >= -0.005
        and concentration["passes"]
    ):
        return (
            "Scenario qualifies for a live validation test",
            "Qualified listening improves by more than 1 pp at the lower confidence bound; "
            "skip, repeat-listening, and artist-diversity checks pass.",
        )
    return (
        "Hold the simulated rollout",
        "The scenario does not meet all benefit and guardrail confidence-bound criteria.",
    )


def write_decision_memo(
    path: Path,
    summary: pd.DataFrame,
    segments: pd.DataFrame,
    srm: dict,
    power: dict,
    diversity: pd.DataFrame,
    metadata: dict,
    concentration: dict,
) -> None:
    decision, rationale = choose_recommendation(summary, srm, concentration)
    primary = _metric_row(summary, "qualified_listen_rate")
    table_rows = []
    for row in summary.itertuples():
        table_rows.append(
            [
                row.metric_label,
                f"{row.control_rate:.1%}",
                f"{row.treatment_rate:.1%}",
                f"{row.absolute_lift * 100:+.1f} pp",
                f"{row.ci_lower * 100:+.1f} to {row.ci_upper * 100:+.1f} pp",
            ]
        )
    scope = (
        f"Simulated campaign outcomes over {metadata['experiment_rows']:,} session opportunities "
        f"from {metadata['listeners']} listeners. Historical Last.fm listening supplies context; "
        "no real promotion ran."
        if metadata["source_mode"] == "lastfm_real_context"
        else "Entirely synthetic CI fixture; no real listening or campaign observations."
    )
    interpretation = (
        f"The generated scenario changes qualified listening by "
        f"{primary['absolute_lift'] * 100:+.1f} percentage points. "
        "This answers the measurement question within the simulator. It is not evidence "
        "of commercial lift. " + rationale
    )
    health = (
        f"SRM p={srm['p_value']:.3f} ({srm['control']:,} control / "
        f"{srm['treatment']:,} treatment). Artist HHI changes "
        f"{concentration['relative_change']:+.1%}, with a 95% interval of "
        f"{concentration['ci_lower']:+.1%} to {concentration['ci_upper']:+.1%}; "
        "the allowed relative increase is 10%. Confidence intervals resample listeners."
    )
    plan = (
        "Before a live test, log eligible exposures, playback/skip timing, saves, and complete "
        "seven-day follow-up. Randomize by listener to avoid cross-session carryover. "
        "Pre-register qualified listening and guardrail tolerances; use a separate pilot "
        "to estimate listener-level variance and size the test. "
        f"The IID approximation here is {power['absolute_mde'] * 100:.1f} pp at 80% power; "
        "it ignores clustering and is not a live-test sample-size commitment."
    )
    limits = (
        "The candidate tracks were already scrobbled, so the opportunity pool is selected. "
        "Track age is observed tenure, not release age; artist popularity is prior sample reach. "
        "Only 50 historical listeners support the real-context analysis. Segments are exploratory "
        "with BH-adjusted p-values, not evidence that one segment beats another. "
        "Simulated outcomes assume no carryover or interference."
    )
    headers = ["Metric", "Control", "Treatment", "Change", "95% CI"]
    table = "| " + " | ".join(headers) + " |\n| --- | ---: | ---: | ---: | --- |\n"
    table += "\n".join("| " + " | ".join(row) + " |" for row in table_rows)
    memo = (
        f"# Music Promotion Experiment Lab: decision memo\n\n**{decision}**\n\n{scope}\n\n"
        f"{table}\n\n## Interpretation\n\n{interpretation}\n\n{health}\n\n"
        f"## Next decision\n\n{plan}\n\n## Limits\n\n{limits}\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(memo, encoding="utf-8")
    table_html = "<tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in headers) + "</tr>"
    for row in table_rows:
        table_html += "<tr>" + "".join(f"<td>{html.escape(v)}</td>" for v in row) + "</tr>"
    content = f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Decision memo | Music Promotion Experiment Lab</title>
<style>body{{font:15px/1.5 system-ui;color:#192723;max-width:850px;margin:32px auto;padding:0 20px}}
h1{{font-size:25px}}h2{{font-size:17px;margin-bottom:6px}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
td,th{{padding:8px;border-bottom:1px solid #cbd5d1;text-align:left}}a{{color:#176b50}}
.table-wrap{{overflow-x:auto}}@media print{{@page{{size:letter;margin:0.5in}}
nav{{display:none}}body{{font-size:11px;line-height:1.4;margin:0;padding:0}}
h1{{font-size:21px}}table{{font-size:10px}}}}</style>
<nav><a href="index.html">Back to experiment</a></nav>
<h1>Music promotion: decision memo</h1><p><strong>{html.escape(decision)}</strong></p>
<p>{html.escape(scope)}</p><div class="table-wrap"><table>{table_html}</table></div>
<h2>Interpretation</h2><p>{html.escape(interpretation)}</p><p>{html.escape(health)}</p>
<h2>Next decision</h2><p>{html.escape(plan)}</p>
<h2>Limits</h2><p>{html.escape(limits)}</p></html>"""
    (path.parents[1] / "docs" / "memo.html").write_text(content, encoding="utf-8")


def write_dashboard_data(
    path: Path,
    summary: pd.DataFrame,
    segments: pd.DataFrame,
    srm: dict,
    power: dict,
    diversity: pd.DataFrame,
    metadata: dict,
    concentration: dict,
) -> None:
    decision, rationale = choose_recommendation(summary, srm, concentration)
    payload = {
        "generatedAt": metadata["generated_at"],
        "sourceMode": metadata["source_mode"],
        "experimentRows": metadata["experiment_rows"],
        "listeners": metadata["listeners"],
        "decision": decision,
        "rationale": rationale,
        "summary": json.loads(summary.to_json(orient="records")),
        "segments": json.loads(segments.to_json(orient="records")),
        "srm": srm,
        "power": power,
        "concentration": concentration,
        "diversity": json.loads(diversity.to_json(orient="records")),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "window.EXPERIMENT_DATA = " + json.dumps(payload, indent=2, allow_nan=False) + ";\n",
        encoding="utf-8",
    )
