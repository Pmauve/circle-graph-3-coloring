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


def runtime_vs_size_figure(data: BenchmarkReportData) -> go.Figure:
    """Build a runtime-vs-size scatter plot for timed result rows."""
    figure = go.Figure()
    families = sorted({row.family or "unknown" for row in data.rows})
    family_symbols = {
        family: _MARKER_SYMBOLS[index % len(_MARKER_SYMBOLS)]
        for index, family in enumerate(families)
    }
    grouped: dict[str, list[ReportRow]] = defaultdict(list)
    variant_labels: dict[str, str] = {}
    for row in data.rows:
        if row.wall_time_s is None or row.n is None:
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
                key=lambda row: (row.n, row.instance_id, row.wall_time_s),
            )
        )
        trace_rows_by_variant.append(solver_rows)
        variant_label = variant_labels[variant_key]
        color = solver_target_color(variant_label)
        figure.add_trace(
            go.Scatter(
                x=[row.n for row in solver_rows],
                y=[row.wall_time_s for row in solver_rows],
                mode="markers",
                name=variant_label,
                marker={
                    "color": color,
                    "size": 10,
                    "symbol": [family_symbols[row.family or "unknown"] for row in solver_rows],
                    "line": {"color": "#ffffff", "width": 0.8},
                },
                customdata=[_row_hover_data(row) for row in solver_rows],
                hovertemplate=_runtime_scatter_hovertemplate(),
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
                "buttons": _family_filter_buttons(trace_rows_by_variant, families, family_symbols),
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
        yaxis_title="wall_time_s",
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
        _render_solver_params(row.solver_params),
        row.family,
        row.n,
        row.m,
        row.is_colorable,
        row.status,
    ]


def _runtime_scatter_hovertemplate() -> str:
    return (
        "instance_id=%{customdata[0]}<br>"
        "solver_target=%{customdata[1]}<br>"
        "solver_variant=%{customdata[2]}<br>"
        "solver_params=%{customdata[3]}<br>"
        "family=%{customdata[4]}<br>"
        "n=%{customdata[5]}<br>"
        "m=%{customdata[6]}<br>"
        "wall_time_s=%{y:.6f}<br>"
        "is_colorable=%{customdata[7]}<br>"
        "status=%{customdata[8]}<extra></extra>"
    )


def _family_filter_buttons(
    trace_rows_by_variant: list[tuple[ReportRow, ...]],
    families: list[str],
    family_symbols: dict[str, str],
) -> list[dict[str, object]]:
    buttons = [
        _family_filter_button(
            label="All families",
            family=None,
            trace_rows_by_variant=trace_rows_by_variant,
            family_symbols=family_symbols,
        )
    ]
    buttons.extend(
        _family_filter_button(
            label=family,
            family=family,
            trace_rows_by_variant=trace_rows_by_variant,
            family_symbols=family_symbols,
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
                "y": [[row.wall_time_s for row in rows] for rows in filtered_rows],
                "customdata": [[_row_hover_data(row) for row in rows] for rows in filtered_rows],
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
