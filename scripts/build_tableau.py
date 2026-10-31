"""Create a portable Tableau dashboard using aggregated experiment outputs only."""

from __future__ import annotations

import copy
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd
from tableaudocumentapi import Workbook
from tableauhyperapi import (
    Connection,
    CreateMode,
    HyperProcess,
    Inserter,
    SqlType,
    TableDefinition,
    TableName,
    Telemetry,
)

ROOT = Path(__file__).resolve().parents[1]
FIELDS = {
    "panel": "string",
    "label": "string",
    "value": "real",
    "width": "real",
    "detail": "string",
    "variant": "string",
}


def element(parent, tag, text=None, **attrs):
    node = ET.SubElement(parent, tag, {k.replace("_", "-"): str(v) for k, v in attrs.items()})
    node.text = text
    return node


def rows_for_workbook():
    summary = pd.read_csv(ROOT / "artifacts/experiment_summary.csv")
    segments = pd.read_csv(ROOT / "artifacts/segment_effects.csv")
    srm = pd.read_csv(ROOT / "artifacts/srm_check.csv").iloc[0]
    power = pd.read_csv(ROOT / "artifacts/power_analysis.csv").iloc[0]
    hhi = pd.read_csv(ROOT / "artifacts/diversity_guardrail.csv").iloc[0]
    meta = json.loads((ROOT / "artifacts/analysis_metadata.json").read_text())
    rows = []
    for row in summary.itertuples():
        for arm in ("control", "treatment"):
            rate = getattr(row, arm + "_rate")
            rows.append(
                ["rates", f"{row.metric_label} / {arm}", rate * 100, 0.0, f"{rate:.1%}", arm]
            )
        detail = (
            f"{row.absolute_lift * 100:+.2f} pp; 95% CI "
            f"[{row.ci_lower * 100:+.2f}, {row.ci_upper * 100:+.2f}]"
        )
        rows.append(
            [
                "overall",
                row.metric_label,
                row.ci_lower * 100,
                (row.ci_upper - row.ci_lower) * 100,
                detail,
                "95% interval",
            ]
        )
    for row in segments.loc[segments.metric.eq("qualified_listen_rate")].itertuples():
        label = f"{row.dimension.replace('_segment', '').replace('_', ' ')}: {row.segment}"
        detail = (
            f"{row.absolute_lift * 100:+.2f} pp; 95% CI "
            f"[{row.ci_lower * 100:+.2f}, {row.ci_upper * 100:+.2f}]; q={row.q_value:.3g}"
        )
        rows.append(
            [
                "segments",
                label,
                row.ci_lower * 100,
                (row.ci_upper - row.ci_lower) * 100,
                detail,
                "exploratory",
            ]
        )
    health = {
        "Assignment": f"{int(srm.control):,} control / {int(srm.treatment):,} treatment",
        "SRM p-value": f"{srm.p_value:.3f}; fail below 0.01",
        "Listener clusters": str(meta["listeners"]),
        "IID planning MDE": f"{power.absolute_mde * 100:.2f} pp; ignores clustering",
        "Artist HHI change": f"{hhi.relative_change:+.1%}; 95% CI "
        f"[{hhi.ci_lower:+.1%}, {hhi.ci_upper:+.1%}]",
        "Provenance": f"{meta['source_mode']}; {meta['simulation_version']}",
    }
    rows.extend(["health", label, 0.0, 0.0, detail, "context"] for label, detail in health.items())
    return rows


def build(output: Path = ROOT / "tableau") -> Path:
    output.mkdir(parents=True, exist_ok=True)
    data_dir = output / "Data"
    data_dir.mkdir(exist_ok=True)
    extract = data_dir / "experiment.hyper"
    types = {"string": SqlType.text(), "real": SqlType.double()}
    table = TableDefinition(
        TableName("Extract", "Extract"),
        [TableDefinition.Column(name, types[dtype]) for name, dtype in FIELDS.items()],
    )
    rows = rows_for_workbook()
    with HyperProcess(Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hyper:
        with Connection(hyper.endpoint, str(extract), CreateMode.CREATE_AND_REPLACE) as connection:
            connection.catalog.create_schema("Extract")
            connection.catalog.create_table(table)
            with Inserter(connection, table) as inserter:
                inserter.add_rows(rows)
                inserter.execute()
            assert connection.execute_scalar_query(
                'SELECT COUNT(*) FROM "Extract"."Extract"'
            ) == len(rows)

    wb = ET.Element(
        "workbook",
        {
            "version": "18.1",
            "source-platform": "win",
            "original-version": "18.1",
            "source-build": "0.0.0 (generated)",
        },
    )
    preferences = element(wb, "preferences")
    element(preferences, "preference", name="ui.encoding.shelf.height", value="24")
    sources = element(wb, "datasources")
    source = element(
        sources,
        "datasource",
        caption="Simulated promotion experiment",
        inline="true",
        name="experiment",
        version="18.1",
    )
    connection = element(
        source,
        "connection",
        **{
            "class": "hyper",
            "dbname": "Data/experiment.hyper",
            "schema": "Extract",
            "access_mode": "readonly",
        },
    )
    element(connection, "relation", name="Extract", table="[Extract].[Extract]", type="table")
    columns = {}
    for name, dtype in FIELDS.items():
        columns[name] = element(
            source,
            "column",
            name=f"[{name}]",
            datatype=dtype,
            role="dimension" if dtype == "string" else "measure",
            type="nominal" if dtype == "string" else "quantitative",
        )
    worksheets = element(wb, "worksheets")
    specifications = [
        ("Rates (%)", "rates", "Bar"),
        ("Overall lift - 95% intervals (pp)", "overall", "GanttBar"),
        ("Qualified listening by segment - exploratory (pp)", "segments", "GanttBar"),
        ("Experiment health", "health", "Text"),
    ]
    for title, panel, mark in specifications:
        sheet = element(worksheets, "worksheet", name=title)
        layout = element(sheet, "layout-options")
        element(element(element(layout, "title"), "formatted-text"), "run", title)
        table_node = element(sheet, "table")
        view = element(table_node, "view")
        element(
            element(view, "datasources"),
            "datasource",
            name="experiment",
            caption="Simulated promotion experiment",
        )
        dependencies = element(view, "datasource-dependencies", datasource="experiment")
        for name, col in columns.items():
            dependencies.append(copy.deepcopy(col))
            numeric = FIELDS[name] == "real"
            element(
                dependencies,
                "column-instance",
                column=f"[{name}]",
                derivation="Avg" if numeric else "None",
                name=f"[{'avg' if numeric else 'none'}:{name}:{'qk' if numeric else 'nk'}]",
                pivot="key",
                type="quantitative" if numeric else "nominal",
            )
        filter_node = element(
            view, "filter", **{"class": "categorical", "column": "[experiment].[none:panel:nk]"}
        )
        element(
            filter_node,
            "groupfilter",
            function="member",
            level="[none:panel:nk]",
            member=f'"{panel}"',
        )
        element(view, "aggregation", value="true")
        style = element(table_node, "style")
        element(
            element(style, "style-rule", element="cell"), "format", attr="font-size", value="11"
        )
        pane = element(
            element(table_node, "panes"),
            "pane",
            selection_relaxation_option="selection-relaxation-allow",
        )
        element(element(pane, "view"), "breakdown", value="auto")
        element(pane, "mark", **{"class": mark})
        encodings = element(pane, "encodings")
        if mark == "GanttBar":
            element(encodings, "size", column="[experiment].[avg:width:qk]")
        if mark == "Bar":
            element(encodings, "color", column="[experiment].[none:variant:nk]")
        element(
            encodings, "text" if mark == "Text" else "lod", column="[experiment].[none:detail:nk]"
        )
        pane_style = element(pane, "style")
        element(
            element(pane_style, "style-rule", element="mark"),
            "format",
            attr="mark-color",
            value="#137a57",
        )
        element(table_node, "rows", "[experiment].[none:label:nk]")
        element(table_node, "cols", "" if mark == "Text" else "[experiment].[avg:value:qk]")
        element(sheet, "simple-id", uuid="{" + str(uuid5(NAMESPACE_URL, title)).upper() + "}")

    dashboard = element(element(wb, "dashboards"), "dashboard", name="Promotion Quality Review")
    element(dashboard, "style")
    element(dashboard, "size", maxheight="1100", maxwidth="1280", minheight="1100", minwidth="1280")
    zones = element(dashboard, "zones")
    title_zone = element(
        zones, "zone", id="1", type_v2="text", x="2000", y="1000", w="96000", h="9000"
    )
    formatted = element(title_zone, "formatted-text")
    element(formatted, "run", "Music Promotion Experiment Lab\n", bold="true", fontsize="24")
    element(
        formatted,
        "run",
        "SIMULATED CAMPAIGN OUTCOMES | Historical Last.fm context\n"
        "A measurement case study, not evidence of real campaign lift.",
        fontsize="12",
    )
    positions = [
        (2000, 11000, 46000, 37000),
        (51000, 11000, 47000, 37000),
        (2000, 50000, 96000, 27000),
        (2000, 79000, 96000, 19000),
    ]
    for i, ((title, _, _), (x, y, width, height)) in enumerate(
        zip(specifications, positions, strict=True), 2
    ):
        element(zones, "zone", id=str(i), name=title, x=x, y=y, w=width, h=height)
    element(
        dashboard,
        "simple-id",
        uuid="{" + str(uuid5(NAMESPACE_URL, "promotion-dashboard")).upper() + "}",
    )
    windows = element(wb, "windows")
    for title, _, _ in specifications:
        window = element(windows, "window", **{"class": "worksheet", "name": title})
        viewpoints = element(window, "viewpoints")
        element(element(viewpoints, "viewpoint", name=title), "zoom", type="entire-view")
        element(window, "active", id="-1")
    window = element(
        windows, "window", **{"class": "dashboard", "name": "Promotion Quality Review"}
    )
    viewpoints = element(window, "viewpoints")
    for title, _, _ in specifications:
        element(element(viewpoints, "viewpoint", name=title), "zoom", type="entire-view")
    element(window, "active", id="-1")
    explain = element(
        wb, "explain-data", enabled_for_viewer="false", extreme_values_enabled_for_all="false"
    )
    element(explain, "explanation-types")
    ET.indent(wb)
    workbook = output / "Music-Promotion-Experiment-Lab.twb"
    ET.ElementTree(wb).write(workbook, encoding="utf-8", xml_declaration=True)
    package = output / "Music-Promotion-Experiment-Lab.twbx"
    with ZipFile(package, "w", ZIP_DEFLATED) as archive:
        archive.write(workbook, workbook.name)
        archive.write(extract, "Data/experiment.hyper")
    checked = Workbook(str(package))
    assert len(checked.worksheets) == 4
    assert len(checked.datasources) == 1
    print(f"Built {package.name}: {len(rows)} aggregate rows, 4 worksheets, 1 dashboard.")
    print(
        "Package and extract validated; open in Tableau Public "
        "for visual verification and publishing."
    )
    return package


if __name__ == "__main__":
    sys.exit(0 if build().exists() else 1)
