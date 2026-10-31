(() => {
  "use strict";

  const data = window.EXPERIMENT_DATA;
  const metricControl = document.querySelector("#metric-control");
  const dimensionControl = document.querySelector("#dimension-control");
  const metricOrder = [
    "qualified_listen_rate",
    "play_rate",
    "save_rate",
    "repeat_7d_rate",
    "skip_rate"
  ];
  const dimensionLabels = {
    listener_segment: "Listener",
    track_age_segment: "Track tenure",
    artist_popularity_segment: "Artist reach"
  };
  let activeMetric = metricOrder.find((metric) => data.summary.some((row) => row.metric === metric));
  let activeDimension = Object.keys(dimensionLabels).find((dimension) =>
    data.segments.some((row) => row.dimension === dimension)
  );

  const formatPercent = (value) => `${(Number(value) * 100).toFixed(1)}%`;
  const formatPp = (value) => {
    const number = Number(value) * 100;
    return `${number >= 0 ? "+" : ""}${number.toFixed(1)} pp`;
  };
  const formatP = (value) => Number(value) < 0.001 ? "<0.001" : Number(value).toFixed(3);
  const pretty = (value) => String(value).replaceAll("_", " ").replace("+", "+");

  function renderHealth() {
    document.querySelector("#decision-title").textContent = data.decision;
    document.querySelector("#decision-rationale").textContent = data.rationale;
    document.querySelector("#source-mode").textContent = pretty(data.sourceMode);
    document.querySelector("#opportunity-count").textContent = Number(data.experimentRows).toLocaleString();
    document.querySelector("#treatment-share").textContent = formatPercent(data.srm.treatment_share || 0);
    document.querySelector("#srm-value").textContent = formatP(data.srm.p_value || 0);
    document.querySelector("#mde-value").textContent = formatPp(data.power.absolute_mde || 0);
    const generated = data.generatedAt === "pending" ? "Pipeline not run" : new Date(data.generatedAt).toLocaleString();
    document.querySelector("#generated-at").textContent = `Generated ${generated}`;
  }

  function makeButton(label, pressed, onClick) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.setAttribute("aria-pressed", String(pressed));
    button.addEventListener("click", onClick);
    return button;
  }

  function renderControls() {
    metricControl.replaceChildren();
    data.summary
      .filter((row) => metricOrder.includes(row.metric))
      .sort((a, b) => metricOrder.indexOf(a.metric) - metricOrder.indexOf(b.metric))
      .forEach((row) => {
        metricControl.append(makeButton(row.metric_label, row.metric === activeMetric, () => {
          activeMetric = row.metric;
          renderControls();
          renderMetric();
          renderSegments();
        }));
      });

    dimensionControl.replaceChildren();
    Object.entries(dimensionLabels).forEach(([key, label]) => {
      if (!data.segments.some((row) => row.dimension === key)) return;
      dimensionControl.append(makeButton(label, key === activeDimension, () => {
        activeDimension = key;
        renderControls();
        renderSegments();
      }));
    });
  }

  function renderMetric() {
    const metric = data.summary.find((row) => row.metric === activeMetric);
    if (!metric) return;
    const comparison = document.querySelector("#rate-comparison");
    const maximum = Math.max(metric.control_rate, metric.treatment_rate, 0.01) * 1.12;
    comparison.replaceChildren();
    [
      ["Control", metric.control_rate, "control"],
      ["Treatment", metric.treatment_rate, "treatment"]
    ].forEach(([label, value, className]) => {
      const row = document.createElement("div");
      row.className = "rate-row";
      row.innerHTML = `
        <span class="rate-label">${label}</span>
        <span class="rate-track"><span class="rate-fill ${className}" style="width:${Math.max(1, value / maximum * 100)}%"></span></span>
        <span class="rate-value">${formatPercent(value)}</span>`;
      comparison.append(row);
    });
    document.querySelector("#effect-value").textContent = formatPp(metric.absolute_lift);
    document.querySelector("#effect-ci").textContent = `95% CI ${formatPp(metric.ci_lower)} to ${formatPp(metric.ci_upper)}`;
    document.querySelector("#effect-q").textContent = `Adjusted q-value ${formatP(metric.q_value)}`;
  }

  function svgElement(name, attributes = {}) {
    const node = document.createElementNS("http://www.w3.org/2000/svg", name);
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, String(value)));
    return node;
  }

  function renderForest(rows) {
    const svg = document.querySelector("#forest-plot");
    const width = Math.max(svg.clientWidth, 300);
    const height = Math.max(260, rows.length * 58 + 86);
    const left = width < 520 ? 100 : 190;
    const right = width < 520 ? 65 : 100;
    const top = 35;
    const values = rows.flatMap((row) => [row.ci_lower, row.ci_upper, row.absolute_lift, 0]);
    let min = Math.min(...values);
    let max = Math.max(...values);
    const padding = Math.max((max - min) * 0.15, 0.01);
    min -= padding;
    max += padding;
    const x = (value) => left + ((value - min) / (max - min)) * (width - left - right);
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.style.height = `${height}px`;
    svg.replaceChildren();

    const zero = svgElement("line", {x1: x(0), x2: x(0), y1: top - 15, y2: height - 42, class: "zero-line"});
    svg.append(zero);
    rows.forEach((row, index) => {
      const y = top + index * 58 + 24;
      const label = svgElement("text", {x: 0, y: y + 4, class: "segment-label"});
      label.textContent = pretty(row.segment);
      const ci = svgElement("line", {x1: x(row.ci_lower), x2: x(row.ci_upper), y1: y, y2: y, class: "ci-line"});
      const capLeft = svgElement("line", {x1: x(row.ci_lower), x2: x(row.ci_lower), y1: y - 6, y2: y + 6, class: "ci-line"});
      const capRight = svgElement("line", {x1: x(row.ci_upper), x2: x(row.ci_upper), y1: y - 6, y2: y + 6, class: "ci-line"});
      const dot = svgElement("circle", {
        cx: x(row.absolute_lift), cy: y, r: 6,
        class: `effect-dot ${row.ci_lower <= 0 && row.ci_upper >= 0 ? "uncertain" : ""}`
      });
      const value = svgElement("text", {x: width - right + 8, y: y + 4, class: "axis-label"});
      value.textContent = formatPp(row.absolute_lift);
      svg.append(label, ci, capLeft, capRight, dot, value);
    });
    [min, 0, max].forEach((tick) => {
      const label = svgElement("text", {x: x(tick), y: height - 16, class: "axis-label", "text-anchor": "middle"});
      label.textContent = formatPp(tick);
      svg.append(label);
    });
  }

  function renderSegments() {
    const rows = data.segments
      .filter((row) => row.metric === activeMetric && row.dimension === activeDimension)
      .sort((a, b) => b.absolute_lift - a.absolute_lift);
    if (!rows.length) return;
    renderForest(rows);
    const body = document.querySelector("#segment-table");
    body.replaceChildren();
    rows.forEach((row) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${pretty(row.segment)}</td>
        <td>${formatPercent(row.control_rate)}</td>
        <td>${formatPercent(row.treatment_rate)}</td>
        <td>${formatPp(row.absolute_lift)}</td>
        <td>${formatPp(row.ci_lower)} to ${formatPp(row.ci_upper)}</td>
        <td>${formatP(row.q_value)}</td>`;
      body.append(tr);
    });
  }

  renderHealth();
  window.addEventListener("resize", () => renderSegments());
  if (activeMetric && activeDimension) {
    renderControls();
    renderMetric();
    renderSegments();
  }
})();

