import json

from jinja2 import Environment, select_autoescape
import plotly.graph_objects as go
from plotly.io import to_html

from three_col_circle_code.bench.report_data import BenchmarkReportData, build_report_plot_payload


_TEMPLATE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ title }}</title>
    <style>
      :root {
        color-scheme: light;
        --bg: #f7f7f5;
        --card: #ffffff;
        --text: #202225;
        --muted: #5d6470;
        --border: #d7dbe2;
        --accent: #2f4f6f;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        padding: 24px;
        background: var(--bg);
        color: var(--text);
        font-family: "Segoe UI", Tahoma, sans-serif;
        line-height: 1.5;
      }
      main { max-width: 1640px; margin: 0 auto; }
      h1, h2 { margin: 0; }
      h1 { font-size: 1.8rem; }
      h2 { font-size: 1.1rem; color: var(--accent); }
      p { color: var(--muted); }
      .section {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 18px;
        margin-bottom: 14px;
      }
      .section-header {
        margin-bottom: 14px;
      }
      .metrics {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 10px;
      }
      .metric {
        padding: 12px;
        border: 1px solid var(--border);
        border-radius: 8px;
        background: #fafbfc;
      }
      .metric strong {
        display: block;
        font-size: 1.2rem;
        color: var(--text);
      }
      table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.95rem;
      }
      th, td {
        text-align: left;
        padding: 9px 10px;
        border-bottom: 1px solid var(--border);
        vertical-align: top;
      }
      th {
        font-size: 0.9rem;
        color: var(--accent);
        font-weight: 600;
      }
      .mono {
        font-family: "Consolas", "Courier New", monospace;
        font-size: 0.92rem;
      }
      .subtle {
        margin: 6px 0 0;
      }
      .table-wrap {
        overflow-x: auto;
      }
      .solver-summary {
        table-layout: fixed;
        font-size: 0.88rem;
      }
      .solver-summary th,
      .solver-summary td {
        white-space: nowrap;
      }
      .solver-summary .solver-label {
        white-space: normal;
        width: 32%;
      }
      .solver-summary .status-cell {
        width: 16%;
      }
      .solver-summary .numeric {
        text-align: right;
      }
      .plot-wrap {
        overflow-x: auto;
      }
      #runtime-vs-size-plot,
      #memory-vs-size-plot {
        width: 100%;
        min-height: 680px;
      }
      .plot-controls {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 12px 22px;
        align-items: start;
        margin: 8px 0 16px;
      }
      .control-stack {
        display: grid;
        gap: 8px;
      }
      .families-control {
        justify-content: flex-end;
        max-width: min(720px, 100%);
      }
      .control-group {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        align-items: center;
      }
      .control-label {
        color: var(--muted);
        font-size: 0.92rem;
        font-weight: 600;
        margin-right: 6px;
      }
      .control-option {
        position: relative;
        display: inline-flex;
        align-items: center;
        color: var(--text);
        cursor: pointer;
        font-size: 0.92rem;
        white-space: nowrap;
      }
      .control-option input {
        position: absolute;
        opacity: 0;
        pointer-events: none;
      }
      .control-text {
        border: 1px solid var(--border);
        background: #ffffff;
        color: var(--text);
        min-height: 32px;
        padding: 5px 10px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        line-height: 1.2;
        pointer-events: none;
      }
      .family-symbol {
        display: inline-block;
        margin-right: 6px;
        font-size: 0.9em;
        line-height: 1;
      }
      .segmented-control {
        gap: 0;
      }
      .segmented-option .control-text {
        border-left-width: 0;
      }
      .segmented-option:first-of-type .control-text {
        border-left-width: 1px;
        border-radius: 6px 0 0 6px;
      }
      .segmented-option:last-child .control-text {
        border-radius: 0 6px 6px 0;
      }
      .chip-control {
        gap: 8px;
      }
      .chip-option .control-text {
        border-radius: 999px;
        padding-inline: 11px;
      }
      .control-option input:checked + .control-text {
        border-color: var(--accent);
        background: var(--accent);
        color: #ffffff;
      }
      .control-option input:focus-visible + .control-text {
        outline: 2px solid #7aa7d9;
        outline-offset: 2px;
      }
      .control-option:has(input:disabled) {
        color: var(--muted);
        cursor: default;
        opacity: 0.55;
      }
      .control-option:has(input:disabled) .control-text {
        background: #f3f5f7;
      }
      .plot-title {
        margin: 10px 0 4px;
        color: var(--muted);
        font-size: 0.95rem;
        font-weight: 600;
      }
      .plotly-bootstrap {
        display: none;
      }
      @media (max-width: 720px) {
        body { padding: 16px; }
        .section { padding: 14px; }
        .plot-controls { grid-template-columns: 1fr; }
        .families-control { justify-content: flex-start; }
      }
    </style>
  </head>
  <body>
    <main>
      <section class="section">
        <div class="section-header">
        <h1>{{ title }}</h1>
        <p class="subtle">Single benchmark run summary.</p>
        </div>
        <div class="table-wrap">
        <table>
          <tbody>
            <tr><th>Run ID</th><td class="mono">{{ metadata.run_id }}</td></tr>
            <tr><th>Created At</th><td>{{ metadata.created_at or "Unavailable" }}</td></tr>
            <tr><th>Instances</th><td>{{ metadata.n_instances }}</td></tr>
            <tr><th>Tasks</th><td>{{ metadata.n_tasks }}</td></tr>
            <tr><th>Solver Variants</th><td class="mono">{{ metadata.solver_targets | join(", ") }}</td></tr>
          </tbody>
        </table>
        </div>
      </section>

      <section class="section">
        <div class="section-header">
        <h2>Headline Stats</h2>
        </div>
        <div class="metrics">
          <div class="metric"><strong>{{ headline.n_unanimous_agreements }}</strong>Unanimous agreements</div>
          <div class="metric"><strong>{{ headline.n_disagreements }}</strong>Disagreements</div>
          <div class="metric"><strong>{{ headline.n_ok }}</strong>ok rows</div>
          <div class="metric"><strong>{{ headline.n_error }}</strong>error rows</div>
          <div class="metric"><strong>{{ headline.n_invalid }}</strong>invalid rows</div>
          <div class="metric"><strong>{{ headline.best_median_runtime_solver_target or "n/a" }}</strong>Best median runtime solver</div>
        </div>
      </section>

      <section class="section">
        <div class="section-header">
        <h2>Runtime vs Size</h2>
        </div>
        <div class="plot-controls" id="runtime-controls">
          <div class="control-stack">
            <div class="control-group segmented-control" id="runtime-metric-controls">
              <span class="control-label">Metric</span>
            </div>
            <div class="control-group segmented-control" id="runtime-scale-controls">
              <span class="control-label">Y scale</span>
            </div>
          </div>
          <div class="control-group chip-control families-control" id="runtime-family-controls">
            <span class="control-label">Families</span>
          </div>
        </div>
        <div class="plot-wrap"><div id="runtime-vs-size-plot"></div></div>
        <h3 class="plot-title">Peak Memory vs Size</h3>
        <div class="plot-controls" id="memory-controls">
          <div class="control-stack">
            <div class="control-group segmented-control" id="memory-scale-controls">
              <span class="control-label">Y scale</span>
            </div>
          </div>
          <div class="control-group chip-control families-control" id="memory-family-controls">
            <span class="control-label">Families</span>
          </div>
        </div>
        <div class="plot-wrap"><div id="memory-vs-size-plot"></div></div>
      </section>

      <section class="section">
        <div class="section-header">
        <h2>Solver Summary</h2>
        </div>
        <div class="table-wrap">
        <table class="solver-summary">
          <thead>
            <tr>
              <th class="solver-label">Solver Variant</th>
              <th class="status-cell">ok/error/invalid</th>
              <th class="numeric">Wall med</th>
              <th class="numeric">Native med</th>
              <th class="numeric">RSS max</th>
            </tr>
          </thead>
          <tbody>
            {% for row in solver_summary_rows %}
            <tr>
              <td class="mono solver-label">{{ row.solver_target }}</td>
              <td class="status-cell">{{ row.n_ok }}/{{ row.n_error }}/{{ row.n_invalid }}</td>
              <td class="numeric">{{ format_seconds(row.median_wall_time_s) }}</td>
              <td class="numeric">{{ format_seconds(row.median_total_native_time_s) }}</td>
              <td class="numeric">{{ format_mb(row.max_peak_rss_kb) }}</td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
        </div>
      </section>

      <section class="section">
        <div class="section-header">
        <h2>Disagreements</h2>
        </div>
        {% if disagreement_rows %}
        <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Instance ID</th>
              <th>Family</th>
              <th>Bucket</th>
              <th>n</th>
              <th>Statuses</th>
              <th>Answers</th>
            </tr>
          </thead>
          <tbody>
            {% for row in disagreement_rows %}
            <tr>
              <td class="mono">{{ row.instance_id }}</td>
              <td>{{ row.family or "n/a" }}</td>
              <td>{{ row.bucket or "n/a" }}</td>
              <td>{{ row.n if row.n is not none else "n/a" }}</td>
              <td>{{ row.statuses_summary }}</td>
              <td>{{ row.answers_summary }}</td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
        </div>
        {% else %}
        <p>No disagreements found in this run.</p>
        {% endif %}
      </section>
    </main>
    <div class="plotly-bootstrap">{{ plotly_bootstrap_html | safe }}</div>
    <script id="benchmark-plot-data" type="application/json">{{ plot_payload_json | safe }}</script>
    <script>
      (function () {
        const dataElement = document.getElementById("benchmark-plot-data");
        const plotElement = document.getElementById("runtime-vs-size-plot");
        const memoryPlotElement = document.getElementById("memory-vs-size-plot");
        const metricControls = document.getElementById("runtime-metric-controls");
        const scaleControls = document.getElementById("runtime-scale-controls");
        const familyControls = document.getElementById("runtime-family-controls");
        const memoryScaleControls = document.getElementById("memory-scale-controls");
        const memoryFamilyControls = document.getElementById("memory-family-controls");
        if (!dataElement || !plotElement || !memoryPlotElement || !window.Plotly) {
          return;
        }
        const payload = JSON.parse(dataElement.textContent);
        const colors = {{ solver_colors_json | safe }};
        const familySymbols = {{ family_symbols_json | safe }};
        let selectedMetric = "wall_time_s";
        let selectedYScale = "log";
        let selectedMemoryYScale = "log";
        const selectedFamilies = new Set(payload.families);
        const selectedMemoryFamilies = new Set(payload.families);

        function metricHasData(metricKey) {
          return payload.rows.some((row) => row.metrics[metricKey] !== null && row.metrics[metricKey] !== undefined);
        }

        function addMetricControls() {
          payload.metrics.forEach((metric) => {
            const hasData = metricHasData(metric.key);
            const label = document.createElement("label");
            label.className = "control-option segmented-option";
            const input = document.createElement("input");
            input.type = "radio";
            input.name = "runtime_metric";
            input.value = metric.key;
            input.disabled = !hasData;
            input.checked = metric.key === selectedMetric;
            if (!hasData) {
              label.title = "No measurements available in this run";
            }
            input.addEventListener("change", () => {
              selectedMetric = metric.key;
              renderRuntimePlot();
            });
            const text = document.createElement("span");
            text.className = "control-text";
            text.textContent = metric.label;
            label.appendChild(input);
            label.appendChild(text);
            metricControls.appendChild(label);
          });
        }

        function addScaleControls(container, selectedValue, onChange) {
          [
            { key: "linear", label: "Linear" },
            { key: "log", label: "Log" }
          ].forEach((scale) => {
            const label = document.createElement("label");
            label.className = "control-option segmented-option";
            const input = document.createElement("input");
            input.type = "radio";
            input.name = container.id + "_value";
            input.value = scale.key;
            input.checked = scale.key === selectedValue;
            input.addEventListener("change", () => {
              onChange(scale.key);
            });
            const text = document.createElement("span");
            text.className = "control-text";
            text.textContent = scale.label;
            label.appendChild(input);
            label.appendChild(text);
            container.appendChild(label);
          });
        }

        function addFamilyControls(container, selectedSet, onChange) {
          payload.families.forEach((family) => {
            const label = document.createElement("label");
            label.className = "control-option chip-option";
            const input = document.createElement("input");
            input.type = "checkbox";
            input.value = family;
            input.checked = true;
            input.addEventListener("change", () => {
              if (input.checked) {
                selectedSet.add(family);
              } else if (selectedSet.size === 1 && selectedSet.has(family)) {
                input.checked = true;
                return;
              } else {
                selectedSet.delete(family);
              }
              onChange();
            });
            const text = document.createElement("span");
            text.className = "control-text";
            const symbol = document.createElement("span");
            symbol.className = "family-symbol";
            symbol.textContent = familySymbols[family] || "●";
            text.appendChild(symbol);
            text.appendChild(document.createTextNode(family));
            label.appendChild(input);
            label.appendChild(text);
            container.appendChild(label);
          });
        }

        function currentMetric() {
          return payload.metrics.find((metric) => metric.key === selectedMetric) || payload.metrics[0];
        }

        function currentVisibilityBySolver(plot) {
          const visibility = {};
          if (!plot.data) {
            return visibility;
          }
          plot.data.forEach((trace) => {
            const key = trace.legendgroup || trace.name;
            if (key && trace.showlegend !== false) {
              visibility[key] = trace.visible;
            }
          });
          return visibility;
        }

        function visibleFor(previousVisibility, key) {
          return Object.prototype.hasOwnProperty.call(previousVisibility, key)
            ? previousVisibility[key]
            : true;
        }

        function familyLineDash(family) {
          const index = payload.families.indexOf(family);
          const dashes = ["solid", "dash", "dot", "dashdot", "longdash", "longdashdot"];
          return dashes[Math.max(index, 0) % dashes.length];
        }

        function rgbaColor(color, alpha) {
          const hex = String(color || "").replace("#", "");
          if (hex.length === 6) {
            const r = parseInt(hex.slice(0, 2), 16);
            const g = parseInt(hex.slice(2, 4), 16);
            const b = parseInt(hex.slice(4, 6), 16);
            return "rgba(" + r + "," + g + "," + b + "," + alpha + ")";
          }
          return color || "#2f4f6f";
        }

        function aggregateTraceRows(metricKey, selectedFamilySet) {
          return (payload.aggregates || [])
            .filter((row) => selectedFamilySet.has(row.family))
            .filter((row) => row.metrics[metricKey] !== null && row.metrics[metricKey] !== undefined);
        }

        function buildAggregateTraces(metricKey, selectedFamilySet, previousVisibility) {
          const traces = [];
          const grouped = {};
          const legendSolvers = new Set();
          aggregateTraceRows(metricKey, selectedFamilySet).forEach((row) => {
            const key = row.solver + "\u0000" + row.family;
            if (!grouped[key]) {
              grouped[key] = [];
            }
            grouped[key].push(row);
          });
          Object.keys(grouped).sort().forEach((key) => {
            const rows = grouped[key].sort((left, right) => left.n - right.n);
            const solver = rows[0].solver;
            const family = rows[0].family;
            const color = colors[solver] || "#2f4f6f";
            const visible = visibleFor(previousVisibility, solver);
            const dash = familyLineDash(family);
            const showSolverLegend = !legendSolvers.has(solver);
            legendSolvers.add(solver);
            traces.push({
              type: "scatter",
              mode: "lines",
              name: solver + " q25",
              legendgroup: solver,
              showlegend: false,
              visible: visible,
              x: rows.map((row) => row.n),
              y: rows.map((row) => row.metrics[metricKey].q25),
              line: { color: "rgba(0,0,0,0)", width: 0, dash: dash },
              hoverinfo: "skip"
            });
            traces.push({
              type: "scatter",
              mode: "lines",
              name: solver + " IQR",
              legendgroup: solver,
              showlegend: false,
              visible: visible,
              x: rows.map((row) => row.n),
              y: rows.map((row) => row.metrics[metricKey].q75),
              line: { color: "rgba(0,0,0,0)", width: 0, dash: dash },
              fill: "tonexty",
              fillcolor: rgbaColor(color, 0.15),
              hoverinfo: "skip"
            });
            traces.push({
              type: "scatter",
              mode: "lines+markers",
              name: solver,
              legendgroup: solver,
              showlegend: showSolverLegend,
              visible: visible,
              x: rows.map((row) => row.n),
              y: rows.map((row) => row.metrics[metricKey].median),
              line: { color: color, width: 2.2, dash: dash },
              marker: {
                color: color,
                size: 8,
                symbol: rows.map((row) => row.marker_symbol),
                line: { color: "#ffffff", width: 0.8 }
              },
              customdata: rows.map((row) => [
                row.family,
                row.n_rows,
                row.n_ok,
                row.n_error,
                row.n_invalid,
                row.metrics[metricKey].q25,
                row.metrics[metricKey].q75,
                row.metrics[metricKey].count
              ]),
              hovertemplate:
                "solver=" + solver + "<br>" +
                "family=%{customdata[0]}<br>" +
                "n=%{x}<br>" +
                "median=%{y:.6f}<br>" +
                "q25=%{customdata[5]:.6f}<br>" +
                "q75=%{customdata[6]:.6f}<br>" +
                "ok_values=%{customdata[7]}<br>" +
                "rows=%{customdata[1]}, ok=%{customdata[2]}, error=%{customdata[3]}, invalid=%{customdata[4]}<extra></extra>",
              hoverlabel: { align: "left" }
            });
          });
          return traces;
        }

        function renderRuntimePlot() {
          const metric = currentMetric();
          const previousVisibility = currentVisibilityBySolver(plotElement);
          let plottedRows = 0;
          const rawTraces = payload.solvers.map((solver) => {
            const rows = payload.rows
              .filter((row) => row.solver === solver)
              .filter((row) => selectedFamilies.has(row.family))
              .filter((row) => row.metrics[metric.key] !== null && row.metrics[metric.key] !== undefined)
              .sort((left, right) => {
                if (left.n !== right.n) {
                  return left.n - right.n;
                }
                return String(left.instance_id).localeCompare(String(right.instance_id));
              });
            plottedRows += rows.length;
            return {
              type: "scatter",
              mode: "markers",
              name: solver + " raw",
              legendgroup: solver,
              showlegend: false,
              visible: visibleFor(previousVisibility, solver),
              opacity: 0.32,
              x: rows.map((row) => row.n),
              y: rows.map((row) => row.metrics[metric.key]),
              marker: {
                color: colors[solver] || "#2f4f6f",
                size: 6,
                symbol: rows.map((row) => row.marker_symbol),
                line: { color: "#ffffff", width: 0.8 }
              },
              customdata: rows.map((row) => [
                row.instance_id,
                row.family,
                row.m,
                row.average_degree,
                row.is_colorable,
                row.status
              ]),
              hovertemplate:
                "instance_id=%{customdata[0]}<br>" +
                "solver=" + solver + "<br>" +
                "family=%{customdata[1]}<br>" +
                "n=%{x}<br>" +
                "m=%{customdata[2]}<br>" +
                "average_degree=%{customdata[3]:.4f}<br>" +
                metric.y_axis + "=%{y:.6f}<br>" +
                "is_colorable=%{customdata[4]}<br>" +
                "status=%{customdata[5]}<extra></extra>",
              hoverlabel: { align: "left" }
            };
          });
          const traces = [
            ...rawTraces,
            ...buildAggregateTraces(metric.key, selectedFamilies, previousVisibility)
          ];
          const layout = {
            autosize: true,
            height: 680,
            xaxis: { title: "n", autorange: true },
            yaxis: { title: metric.y_axis, type: selectedYScale, autorange: true },
            legend: {
              orientation: "h",
              x: 0.0,
              xanchor: "left",
              y: -0.22,
              yanchor: "top",
              title: { text: "Solver Variant" }
            },
            template: "plotly_white",
            margin: { l: 56, r: 24, t: 36, b: 112 },
            annotations: plottedRows > 0 ? [] : [
              {
                text: "No measurements available for this metric/filter selection",
                x: 0.5,
                y: 0.5,
                xref: "paper",
                yref: "paper",
                showarrow: false,
                font: { color: "#5d6470", size: 14 }
              }
            ],
            uirevision: "runtime-vs-size"
          };
          Plotly.react(plotElement, traces, layout, {
            responsive: true,
            scrollZoom: true,
            displayModeBar: true,
            displaylogo: false
          }).then(() => Plotly.Plots.resize(plotElement));
        }

        function renderMemoryPlot() {
          const previousVisibility = currentVisibilityBySolver(memoryPlotElement);
          let plottedRows = 0;
          const rawTraces = payload.solvers.map((solver) => {
            const rows = payload.rows
              .filter((row) => row.solver === solver)
              .filter((row) => selectedMemoryFamilies.has(row.family))
              .filter((row) => row.metrics.max_peak_rss_mb !== null && row.metrics.max_peak_rss_mb !== undefined)
              .sort((left, right) => {
                if (left.n !== right.n) {
                  return left.n - right.n;
                }
                return String(left.instance_id).localeCompare(String(right.instance_id));
              });
            plottedRows += rows.length;
            return {
              type: "scatter",
              mode: "markers",
              name: solver + " raw",
              legendgroup: solver,
              showlegend: false,
              visible: visibleFor(previousVisibility, solver),
              opacity: 0.32,
              x: rows.map((row) => row.n),
              y: rows.map((row) => row.metrics.max_peak_rss_mb),
              marker: {
                color: colors[solver] || "#2f4f6f",
                size: 6,
                symbol: rows.map((row) => row.marker_symbol),
                line: { color: "#ffffff", width: 0.8 }
              },
              customdata: rows.map((row) => [
                row.instance_id,
                row.family,
                row.m,
                row.average_degree,
                row.metrics.wall_time_s,
                row.is_colorable,
                row.status
              ]),
              hovertemplate:
                "instance_id=%{customdata[0]}<br>" +
                "solver=" + solver + "<br>" +
                "family=%{customdata[1]}<br>" +
                "n=%{x}<br>" +
                "m=%{customdata[2]}<br>" +
                "average_degree=%{customdata[3]:.4f}<br>" +
                "mean_wall_time_s=%{customdata[4]:.6f}<br>" +
                "max_peak_rss_mb=%{y:.3f}<br>" +
                "is_colorable=%{customdata[5]}<br>" +
                "status=%{customdata[6]}<extra></extra>",
              hoverlabel: { align: "left" }
            };
          });
          const traces = [
            ...rawTraces,
            ...buildAggregateTraces("max_peak_rss_mb", selectedMemoryFamilies, previousVisibility)
          ];
          const layout = {
            autosize: true,
            height: 680,
            xaxis: { title: "n", autorange: true },
            yaxis: { title: "max_peak_rss_mb", type: selectedMemoryYScale, autorange: true },
            legend: {
              orientation: "h",
              x: 0.0,
              xanchor: "left",
              y: -0.22,
              yanchor: "top",
              title: { text: "Solver Variant" }
            },
            template: "plotly_white",
            margin: { l: 64, r: 24, t: 36, b: 112 },
            annotations: plottedRows > 0 ? [] : [
              {
                text: "No memory measurements available for this filter selection",
                x: 0.5,
                y: 0.5,
                xref: "paper",
                yref: "paper",
                showarrow: false,
                font: { color: "#5d6470", size: 14 }
              }
            ]
          };
          Plotly.react(memoryPlotElement, traces, layout, {
            responsive: true,
            scrollZoom: true,
            displayModeBar: true,
            displaylogo: false
          }).then(() => Plotly.Plots.resize(memoryPlotElement));
        }

        addMetricControls();
        addScaleControls(scaleControls, selectedYScale, (scale) => {
          selectedYScale = scale;
          renderRuntimePlot();
        });
        addFamilyControls(familyControls, selectedFamilies, renderRuntimePlot);
        addScaleControls(memoryScaleControls, selectedMemoryYScale, (scale) => {
          selectedMemoryYScale = scale;
          renderMemoryPlot();
        });
        addFamilyControls(memoryFamilyControls, selectedMemoryFamilies, renderMemoryPlot);
        renderRuntimePlot();
        renderMemoryPlot();
      }());
    </script>
  </body>
</html>
"""


def render_report_html(
    *,
    data: BenchmarkReportData,
) -> str:
    """Render the benchmark report HTML document."""
    template = Environment(
        autoescape=select_autoescape(default_for_string=True, enabled_extensions=("html",)),
    ).from_string(_TEMPLATE)
    plot_payload = build_report_plot_payload(data)
    solver_colors = {
        solver: _solver_color(solver)
        for solver in plot_payload["solvers"]
    }
    family_symbols = _family_symbols(plot_payload["families"])
    for row in plot_payload["rows"]:
        row["marker_symbol"] = family_symbols.get(row["family"], "circle")
    for row in plot_payload["aggregates"]:
        row["marker_symbol"] = family_symbols.get(row["family"], "circle")
    return template.render(
        title=data.metadata.run_id,
        metadata=data.metadata,
        headline=data.headline_metrics,
        plot_payload_json=_safe_json(plot_payload),
        solver_colors_json=_safe_json(solver_colors),
        family_symbols_json=_safe_json(
            {
                family: _marker_symbol_label(marker_symbol)
                for family, marker_symbol in family_symbols.items()
            }
        ),
        plotly_bootstrap_html=_figure_html(go.Figure(), include_plotlyjs="inline"),
        solver_summary_rows=data.solver_summary_rows,
        disagreement_rows=data.disagreement_rows,
        format_seconds=_format_seconds,
        format_mb=_format_mb,
    )


def _figure_html(figure: object, *, include_plotlyjs: object) -> str:
    return to_html(
        figure,
        full_html=False,
        include_plotlyjs=include_plotlyjs,
        config={
            "responsive": True,
            "scrollZoom": True,
            "displayModeBar": True,
            "displaylogo": False,
        },
        default_width="100%",
    )


def _format_seconds(value: object) -> str:
    if value is None:
        return "n/a"
    seconds = float(value)
    if seconds < 1.0:
        return f"{seconds:.3f}s"
    if seconds < 10.0:
        return f"{seconds:.2f}s"
    return f"{seconds:.1f}s"


def _format_mb(value: object) -> str:
    if value is None:
        return "n/a"
    return f"{float(value) / 1024.0:.1f} MB"


def _safe_json(value: object) -> str:
    return json.dumps(value, sort_keys=True).replace("</", "<\\/")


def _solver_color(solver_target: str) -> str:
    from three_col_circle_code.bench.report_plots import solver_target_color

    return solver_target_color(solver_target)


def _family_symbols(families: list[str]) -> dict[str, str]:
    symbols = (
        "circle",
        "square",
        "diamond",
        "cross",
        "x",
        "triangle-up",
        "triangle-down",
        "triangle-left",
        "triangle-right",
        "pentagon",
        "hexagon",
        "star",
    )
    return {
        family: symbols[index % len(symbols)]
        for index, family in enumerate(families)
    }


def _marker_symbol_label(marker_symbol: str) -> str:
    return {
        "circle": "●",
        "square": "■",
        "diamond": "◆",
        "cross": "+",
        "x": "×",
        "triangle-up": "▲",
        "triangle-down": "▼",
        "triangle-left": "◀",
        "triangle-right": "▶",
        "pentagon": "⬟",
        "hexagon": "⬢",
        "star": "★",
    }.get(marker_symbol, "●")
