from pathlib import Path
from typing import Optional

from three_col_circle_code.bench.report_data import load_benchmark_report_data
from three_col_circle_code.bench.report_html import render_report_html
from three_col_circle_code.bench.report_plots import runtime_vs_memory_figure, runtime_vs_size_figure


def build_benchmark_report(run_dir: Path, output_path: Optional[Path] = None) -> Path:
    """Generate one static HTML report for a benchmark run directory."""
    report_data = load_benchmark_report_data(run_dir)
    rendered_html = render_report_html(
        data=report_data,
        runtime_vs_size_wall_figure=runtime_vs_size_figure(report_data, metric="wall"),
        runtime_vs_size_core_figure=runtime_vs_size_figure(report_data, metric="core"),
        runtime_vs_memory_figure=runtime_vs_memory_figure(report_data),
    )
    resolved_output_path = Path(output_path) if output_path is not None else Path(run_dir) / "report.html"
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_output_path.write_text(rendered_html, encoding="utf-8")
    return resolved_output_path
