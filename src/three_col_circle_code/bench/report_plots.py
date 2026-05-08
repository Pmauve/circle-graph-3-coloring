import colorsys
import hashlib
import json
from collections import defaultdict
from typing import Any, Optional

import plotly.graph_objects as go

from three_col_circle_code.bench.report_data import (
    BenchmarkReportData,
    ReportRow,
    solver_variant_key,
    solver_variant_label,
)


_MARKER_SYMBOLS = (
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


def runtime_vs_size_figure(data: BenchmarkReportData, *, metric: str = "wall") -> go.Figure:
    """Build a runtime-vs-size scatter plot for timed result rows."""
    if metric not in {"wall", "core"}:
        raise ValueError("metric must be 'wall' or 'core'")
    figure = go.Figure()
    families = sorted({row.family or "unknown" for row in data.rows})
    family_symbols = {
        family: _MARKER_SYMBOLS[index % len(_MARKER_SYMBOLS)]
        for index, family in enumerate(families)
    }
    grouped: dict[str, list[ReportRow]] = defaultdict(list)
    variant_labels: dict[str, str] = {}
    for row in data.rows:
        if _row_metric_value(row, metric) is None or row.n is None:
            continue
        variant_key = solver_variant_key(row.solver_target, row.solver_params)
        grouped[variant_key].append(row)
        variant_labels[variant_key] = solver_variant_label(
            row.solver_target,
            row.solver_params,
            row.solver_label,
        )

    ordered_variant_keys = sorted(grouped, key=lambda key: variant_labels[key])
    trace_rows_by_variant: list[tuple[ReportRow, ...]] = []
    for variant_key in ordered_variant_keys:
        solver_rows = tuple(
            sorted(
                grouped[variant_key],
                key=lambda row: (row.n, row.instance_id, _row_metric_value(row, metric)),
            )
        )
        trace_rows_by_variant.append(solver_rows)
        variant_label = variant_labels[variant_key]
        color = solver_target_color(variant_label)
        figure.add_trace(
            go.Scatter(
                x=[row.n for row in solver_rows],
                y=[_row_metric_value(row, metric) for row in solver_rows],
                mode="markers",
                name=variant_label,
                marker={
                    "color": color,
                    "size": 10,
                    "symbol": [family_symbols[row.family or "unknown"] for row in solver_rows],
                    "line": {"color": "#ffffff", "width": 0.8},
                },
                customdata=[_row_hover_data(row) for row in solver_rows],
                hovertemplate=_runtime_scatter_hovertemplate(metric),
                hoverlabel={"align": "left"},
            )
        )

    figure.update_layout(
        updatemenus=[
            {
                "type": "dropdown",
                "direction": "down",
                "x": 1.0,
                "xanchor": "right",
                "y": 1.16,
                "yanchor": "top",
                "buttons": _family_filter_buttons(trace_rows_by_variant, families, family_symbols, metric),
            },
            {
                "type": "buttons",
                "direction": "right",
                "showactive": True,
                "x": 0.08,
                "xanchor": "left",
                "y": 1.16,
                "yanchor": "top",
                "buttons": _axis_scale_buttons(axis_name="yaxis"),
                "active": 1,
            },
        ]
    )
    figure.add_annotation(
        text="Family",
        x=0.82,
        y=1.17,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"color": "#5d6470", "size": 12},
    )
    figure.add_annotation(
        text="Y scale",
        x=0.0,
        y=1.17,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"color": "#5d6470", "size": 12},
    )
    figure.update_layout(
        xaxis_title="n",
        yaxis_title=f"mean_{metric}_time_s",
        legend={
            "orientation": "h",
            "x": 0.0,
            "xanchor": "left",
            "y": -0.22,
            "yanchor": "top",
            "title": {"text": "Solver Variant"},
        },
        template="plotly_white",
        margin={"l": 56, "r": 24, "t": 96, "b": 112},
    )
    figure.update_yaxes(type="log")
    return figure


def runtime_vs_memory_figure(data: BenchmarkReportData) -> go.Figure:
    """Build a size-vs-peak-memory scatter plot for rows with RSS data."""
    figure = go.Figure()
    families = sorted({row.family or "unknown" for row in data.rows})
    family_symbols = {
        family: _MARKER_SYMBOLS[index % len(_MARKER_SYMBOLS)]
        for index, family in enumerate(families)
    }
    grouped: dict[str, list[ReportRow]] = defaultdict(list)
    variant_labels: dict[str, str] = {}
    for row in data.rows:
        if row.n is None or row.max_peak_rss_kb is None:
            continue
        variant_key = solver_variant_key(row.solver_target, row.solver_params)
        grouped[variant_key].append(row)
        variant_labels[variant_key] = solver_variant_label(
            row.solver_target,
            row.solver_params,
            row.solver_label,
        )

    ordered_variant_keys = sorted(grouped, key=lambda key: variant_labels[key])
    trace_rows_by_variant: list[tuple[ReportRow, ...]] = []
    for variant_key in ordered_variant_keys:
        solver_rows = tuple(
            sorted(
                grouped[variant_key],
                key=lambda row: (row.n, row.max_peak_rss_kb, row.instance_id),
            )
        )
        trace_rows_by_variant.append(solver_rows)
        variant_label = variant_labels[variant_key]
        figure.add_trace(
            go.Scatter(
                x=[row.n for row in solver_rows],
                y=[_kb_to_mb(row.max_peak_rss_kb) for row in solver_rows],
                mode="markers",
                name=variant_label,
                marker={
                    "color": solver_target_color(variant_label),
                    "size": 10,
                    "symbol": [family_symbols[row.family or "unknown"] for row in solver_rows],
                    "line": {"color": "#ffffff", "width": 0.8},
                },
                customdata=[_memory_hover_data(row) for row in solver_rows],
                hovertemplate=_memory_hovertemplate(),
                hoverlabel={"align": "left"},
            )
        )

    figure.update_layout(
        updatemenus=[
            {
                "type": "dropdown",
                "direction": "down",
                "x": 1.0,
                "xanchor": "right",
                "y": 1.16,
                "yanchor": "top",
                "buttons": _memory_family_filter_buttons(trace_rows_by_variant, families, family_symbols),
            },
            {
                "type": "buttons",
                "direction": "right",
                "showactive": True,
                "x": 0.08,
                "xanchor": "left",
                "y": 1.16,
                "yanchor": "top",
                "buttons": _axis_scale_buttons(axis_name="xaxis"),
                "active": 0,
            },
            {
                "type": "buttons",
                "direction": "right",
                "showactive": True,
                "x": 0.24,
                "xanchor": "left",
                "y": 1.16,
                "yanchor": "top",
                "buttons": _axis_scale_buttons(axis_name="yaxis"),
                "active": 1,
            },
        ],
        xaxis_title="n",
        yaxis_title="max_peak_rss_mb",
        legend={
            "orientation": "h",
            "x": 0.0,
            "xanchor": "left",
            "y": -0.22,
            "yanchor": "top",
            "title": {"text": "Solver Variant"},
        },
        template="plotly_white",
        margin={"l": 64, "r": 24, "t": 96, "b": 112},
    )
    figure.add_annotation(
        text="Family",
        x=0.82,
        y=1.17,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"color": "#5d6470", "size": 12},
    )
    figure.add_annotation(
        text="X scale",
        x=0.0,
        y=1.17,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"color": "#5d6470", "size": 12},
    )
    figure.add_annotation(
        text="Y scale",
        x=0.16,
        y=1.17,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"color": "#5d6470", "size": 12},
    )
    figure.update_yaxes(type="log")
    return figure


def solver_target_color(solver_target: str) -> str:
    """Map each solver variant label to one stable report color."""
    digest = hashlib.blake2b(solver_target.encode("utf-8"), digest_size=2).digest()
    hue = int.from_bytes(digest, "big") / 65535.0
    red, green, blue = colorsys.hls_to_rgb(hue, 0.46, 0.62)
    return f"#{int(red * 255):02x}{int(green * 255):02x}{int(blue * 255):02x}"


def _row_hover_data(row: ReportRow) -> list[object]:
    return [
        row.instance_id,
        row.solver_target,
        solver_variant_label(row.solver_target, row.solver_params, row.solver_label),
        _render_solver_params_for_hover(row.solver_params),
        row.family,
        row.n,
        row.m,
        row.average_degree,
        row.is_colorable,
        row.status,
    ]


def _runtime_scatter_hovertemplate(metric: str) -> str:
    return (
        "instance_id=%{customdata[0]}<br>"
        "solver=%{customdata[2]}<br>"
        "%{customdata[3]}"
        "family=%{customdata[4]}<br>"
        "n=%{customdata[5]}<br>"
        "m=%{customdata[6]}<br>"
        "average_degree=%{customdata[7]:.4f}<br>"
        f"mean_{metric}_time_s=%{{y:.6f}}<br>"
        "is_colorable=%{customdata[8]}<br>"
        "status=%{customdata[9]}<extra></extra>"
    )


def _memory_hover_data(row: ReportRow) -> list[object]:
    return [
        row.instance_id,
        row.solver_target,
        solver_variant_label(row.solver_target, row.solver_params, row.solver_label),
        _render_solver_params_for_hover(row.solver_params),
        row.family,
        row.n,
        row.m,
        row.average_degree,
        row.mean_wall_time_s,
        _kb_to_mb(row.max_peak_rss_kb),
        row.is_colorable,
        row.status,
    ]


def _memory_hovertemplate() -> str:
    return (
        "instance_id=%{customdata[0]}<br>"
        "solver=%{customdata[2]}<br>"
        "%{customdata[3]}"
        "family=%{customdata[4]}<br>"
        "n=%{customdata[5]}<br>"
        "m=%{customdata[6]}<br>"
        "average_degree=%{customdata[7]:.4f}<br>"
        "mean_wall_time_s=%{customdata[8]:.6f}<br>"
        "max_peak_rss_mb=%{customdata[9]:.3f}<br>"
        "is_colorable=%{customdata[10]}<br>"
        "status=%{customdata[11]}<extra></extra>"
    )


def _family_filter_buttons(
    trace_rows_by_variant: list[tuple[ReportRow, ...]],
    families: list[str],
    family_symbols: dict[str, str],
    metric: str,
) -> list[dict[str, object]]:
    buttons = [
        _family_filter_button(
            label="All families",
            family=None,
            trace_rows_by_variant=trace_rows_by_variant,
            family_symbols=family_symbols,
            metric=metric,
        )
    ]
    buttons.extend(
        _family_filter_button(
            label=family,
            family=family,
            trace_rows_by_variant=trace_rows_by_variant,
            family_symbols=family_symbols,
            metric=metric,
        )
        for family in families
    )
    return buttons


def _family_filter_button(
    *,
    label: str,
    family: Optional[str],
    trace_rows_by_variant: list[tuple[ReportRow, ...]],
    family_symbols: dict[str, str],
    metric: str,
) -> dict[str, object]:
    filtered_rows = [
        tuple(
            row
            for row in rows
            if family is None or (row.family or "unknown") == family
        )
        for rows in trace_rows_by_variant
    ]
    return {
        "label": label,
        "method": "restyle",
        "args": [
            {
                "x": [[row.n for row in rows] for rows in filtered_rows],
                "y": [[_row_metric_value(row, metric) for row in rows] for rows in filtered_rows],
                "customdata": [[_row_hover_data(row) for row in rows] for rows in filtered_rows],
                "marker.symbol": [
                    [family_symbols[row.family or "unknown"] for row in rows]
                    for rows in filtered_rows
                ],
            }
        ],
    }


def _memory_family_filter_buttons(
    trace_rows_by_variant: list[tuple[ReportRow, ...]],
    families: list[str],
    family_symbols: dict[str, str],
) -> list[dict[str, object]]:
    buttons = [
        _memory_family_filter_button(
            label="All families",
            family=None,
            trace_rows_by_variant=trace_rows_by_variant,
            family_symbols=family_symbols,
        )
    ]
    buttons.extend(
        _memory_family_filter_button(
            label=family,
            family=family,
            trace_rows_by_variant=trace_rows_by_variant,
            family_symbols=family_symbols,
        )
        for family in families
    )
    return buttons


def _memory_family_filter_button(
    *,
    label: str,
    family: Optional[str],
    trace_rows_by_variant: list[tuple[ReportRow, ...]],
    family_symbols: dict[str, str],
) -> dict[str, object]:
    filtered_rows = [
        tuple(
            row
            for row in rows
            if family is None or (row.family or "unknown") == family
        )
        for rows in trace_rows_by_variant
    ]
    return {
        "label": label,
        "method": "restyle",
        "args": [
            {
                "x": [[row.n for row in rows] for rows in filtered_rows],
                "y": [[_kb_to_mb(row.max_peak_rss_kb) for row in rows] for rows in filtered_rows],
                "customdata": [[_memory_hover_data(row) for row in rows] for rows in filtered_rows],
                "marker.symbol": [
                    [family_symbols[row.family or "unknown"] for row in rows]
                    for rows in filtered_rows
                ],
            }
        ],
    }


def _axis_scale_buttons(*, axis_name: str) -> list[dict[str, object]]:
    return [
        {
            "label": "Linear",
            "method": "relayout",
            "args": [{f"{axis_name}.type": "linear"}],
        },
        {
            "label": "Log",
            "method": "relayout",
            "args": [{f"{axis_name}.type": "log"}],
        },
    ]


def _render_solver_params(params: dict[str, Any]) -> str:
    if not params:
        return "{}"
    return json.dumps(params, sort_keys=True)


def _render_solver_params_for_hover(params: dict[str, Any]) -> str:
    if not params:
        return ""
    parts = [
        f"{key}={_short_param_value(value)}"
        for key, value in sorted(params.items())
    ]
    return "params:<br>" + "<br>".join(f"  {part}" for part in parts) + "<br>"


def _short_param_value(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        items = [_short_param_value(item) for item in value]
        if len(items) <= 4:
            return "[" + ", ".join(items) + "]"
        return "[" + ", ".join(items[:4]) + f", ... +{len(items) - 4}]"
    if isinstance(value, dict):
        items = sorted(value.items())
        if not items:
            return "{}"
        rendered = [f"{key}: {_short_param_value(item)}" for key, item in items[:4]]
        suffix = "" if len(items) <= 4 else f", ... +{len(items) - 4}"
        return "{" + ", ".join(rendered) + suffix + "}"
    rendered = str(value)
    if len(rendered) > 80:
        return rendered[:77] + "..."
    return rendered


def _row_metric_value(row: ReportRow, metric: str) -> Optional[float]:
    if metric == "core":
        return row.mean_core_time_s
    return row.mean_wall_time_s


def _kb_to_mb(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return value / 1024.0
