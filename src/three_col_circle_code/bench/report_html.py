from jinja2 import Environment, select_autoescape
from plotly.io import to_html

from three_col_circle_code.bench.report_data import BenchmarkReportData


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
      main { max-width: 980px; margin: 0 auto; }
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
      .plot-wrap {
        overflow-x: auto;
      }
      @media (max-width: 720px) {
        body { padding: 16px; }
        .section { padding: 14px; }
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
        <div class="plot-wrap">{{ runtime_vs_size_html | safe }}</div>
      </section>

      <section class="section">
        <div class="section-header">
        <h2>Solver Summary</h2>
        </div>
        <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Solver Variant</th>
              <th>ok</th>
              <th>error</th>
              <th>invalid</th>
              <th>Measured</th>
              <th>ok Measurements</th>
              <th>Mean Runtime</th>
              <th>Median Runtime</th>
            </tr>
          </thead>
          <tbody>
            {% for row in solver_summary_rows %}
            <tr>
              <td class="mono">{{ row.solver_target }}</td>
              <td>{{ row.n_ok }}</td>
              <td>{{ row.n_error }}</td>
              <td>{{ row.n_invalid }}</td>
              <td>{{ row.repetitions }}</td>
              <td>{{ row.ok_repetitions }}</td>
              <td>{{ "%.6f"|format(row.mean_wall_time_s) if row.mean_wall_time_s is not none else "n/a" }}</td>
              <td>{{ "%.6f"|format(row.median_wall_time_s) if row.median_wall_time_s is not none else "n/a" }}</td>
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
  </body>
</html>
"""


def render_report_html(
    *,
    data: BenchmarkReportData,
    runtime_vs_size_figure: object,
) -> str:
    """Render the benchmark report HTML document."""
    template = Environment(
        autoescape=select_autoescape(default_for_string=True, enabled_extensions=("html",)),
    ).from_string(_TEMPLATE)
    return template.render(
        title=data.metadata.run_id,
        metadata=data.metadata,
        headline=data.headline_metrics,
        runtime_vs_size_html=_figure_html(runtime_vs_size_figure, include_plotlyjs="inline"),
        solver_summary_rows=data.solver_summary_rows,
        disagreement_rows=data.disagreement_rows,
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
