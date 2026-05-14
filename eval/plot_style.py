"""Shared plotting conventions for paper figures.

The goal is to make matplotlib output look like a compact academic figure:
vector PDFs, LaTeX-compatible typography, stable family colors, and enough
marker/line variation to remain readable in grayscale print.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


FigureWidth = Literal["single", "double", "wide"]


@dataclass(frozen=True)
class SeriesStyle:
    color: str
    marker: str
    linestyle: str = "-"


FIGURE_SIZES: dict[FigureWidth, tuple[float, float]] = {
    "single": (3.35, 2.35),
    "double": (6.85, 3.0),
    "wide": (6.85, 4.0),
}

DEFAULT_SERIES_STYLE = SeriesStyle(color="#4c78a8", marker="o")

SERIES_STYLES: dict[str, SeriesStyle] = {
    "K4-Free": SeriesStyle("#4c78a8", "o", "-"),
    "Simple-YES": SeriesStyle("#f58518", "s", "-"),
    r"Density-YES ($\alpha=0$)": SeriesStyle("#54a24b", "^", "-"),
    r"Density-YES ($\alpha=1/2$)": SeriesStyle("#e45756", "D", "-"),
    r"Density-YES ($\alpha=1$)": SeriesStyle("#b279a2", "P", "-"),
    r"Density-YES ($\alpha=2$)": SeriesStyle("#9d755d", "X", "-"),
}


def apply_paper_style() -> None:
    """Apply the project-wide matplotlib style for paper figures."""
    import matplotlib as mpl

    mpl.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.02,
            "font.family": "serif",
            "mathtext.fontset": "cm",
            "font.size": 9,
            "axes.labelsize": 9,
            "axes.titlesize": 9,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 7,
            "axes.linewidth": 0.7,
            "lines.linewidth": 1.35,
            "lines.markersize": 4.0,
            "grid.linewidth": 0.35,
            "grid.alpha": 0.35,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )


def figure_size(width: FigureWidth = "double") -> tuple[float, float]:
    return FIGURE_SIZES[width]


def series_style(label: str) -> SeriesStyle:
    return SERIES_STYLES.get(label, DEFAULT_SERIES_STYLE)


def save_paper_figure(fig, path: Path | str) -> None:
    """Save a figure with project defaults and close enough whitespace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(pad=0.2)
    fig.savefig(path)

