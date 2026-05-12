import argparse
import csv
import math
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@dataclass(frozen=True)
class FamilyConfig:
    slug: str
    label: str
    native_family: str
    alpha: Optional[float] = None


FAMILIES = (
    FamilyConfig("k4_free", "K4-Free", "rc_fast"),
    FamilyConfig("simple_yes", "Simple-YES", "rcy_fast"),
    FamilyConfig("density_yes_a0", r"Density-YES ($\alpha=0$)", "rccy_alpha", 0.0),
    FamilyConfig("density_yes_a0p5", r"Density-YES ($\alpha=1/2$)", "rccy_alpha", 0.5),
    FamilyConfig("density_yes_a1", r"Density-YES ($\alpha=1$)", "rccy_alpha", 1.0),
    FamilyConfig("density_yes_a2", r"Density-YES ($\alpha=2$)", "rccy_alpha", 2.0),
)


def main() -> int:
    args = parse_args()
    native_bin = args.native_bin
    if native_bin is None:
        native_bin = default_native_bin()
    output_root = args.output_root
    instance_root = output_root / "instances"
    plot_root = output_root / "plots"
    output_root.mkdir(parents=True, exist_ok=True)
    instance_root.mkdir(parents=True, exist_ok=True)
    plot_root.mkdir(parents=True, exist_ok=True)

    if args.plots_only:
        rows = read_csv(output_root / "generation_stats.csv")
        degree_rows = read_csv(output_root / "degree_samples.csv")
        write_plots(rows, degree_rows, plot_root)
        return 0

    rows: list[dict[str, object]] = []
    degree_rows: list[dict[str, object]] = []
    for family in FAMILIES:
        for n in args.n_values:
            for seed in args.seeds:
                print(f"generate {family.label}, n={n}, seed={seed}", flush=True)
                instance_path = instance_root / family.slug / f"{family.slug}-n{n:05d}-seed{seed}.circle"
                row = generate_or_reuse(
                    native_bin=native_bin,
                    family=family,
                    n=n,
                    seed=seed,
                    instance_path=instance_path,
                    force=args.force,
                    timeout_s=args.timeout_s,
                )
                rows.append(row)
                if row["status"] != "ok":
                    continue
                parsed = parse_circle(instance_path)
                degrees = circle_degrees(parsed.endpoint_order, parsed.n)
                row.update(degree_summary(degrees))
                row["m"] = parsed.m
                row["average_degree"] = 0.0 if parsed.n == 0 else 2.0 * parsed.m / parsed.n
                if not row.get("reused"):
                    row["generation_time_ms"] = 1000.0 * float(row["generation_time_s"])
                if n in args.degree_n:
                    for vertex, degree in enumerate(degrees, start=1):
                        degree_rows.append(
                            {
                                "family": family.slug,
                                "label": family.label,
                                "n": n,
                                "seed": seed,
                                "vertex": vertex,
                                "degree": degree,
                            }
                        )

    write_csv(output_root / "generation_stats.csv", rows)
    write_csv(output_root / "degree_samples.csv", degree_rows)
    write_csv(output_root / "generation_failures.csv", [row for row in rows if row.get("status") != "ok"])
    print_failure_summary(rows)
    write_plots(rows, degree_rows, plot_root)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate paper plots for native circle graph families.")
    parser.add_argument("--output-root", type=Path, default=Path("eval/paper_generator_plots"))
    parser.add_argument("--native-bin", type=Path, default=None)
    parser.add_argument("--n-values", type=int, nargs="+", default=[100, 250, 500, 1000, 2000, 5000, 10000])
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(1, 21)))
    parser.add_argument("--degree-n", type=int, nargs="+", default=[2000])
    parser.add_argument("--timeout-s", type=int, default=180)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--plots-only", action="store_true")
    return parser.parse_args()


def default_native_bin() -> Path:
    suffix = ".exe" if is_windows() else ""
    return Path("native") / "target" / "release" / f"three_col_native{suffix}"


def is_windows() -> bool:
    return "\\" in str(Path.cwd()) or Path("C:/").exists()


def generate_or_reuse(
    *,
    native_bin: Path,
    family: FamilyConfig,
    n: int,
    seed: int,
    instance_path: Path,
    force: bool,
    timeout_s: int,
) -> dict[str, object]:
    instance_path.parent.mkdir(parents=True, exist_ok=True)
    if instance_path.exists() and not force:
        return {
            "family": family.slug,
            "label": family.label,
            "native_family": family.native_family,
            "alpha": "" if family.alpha is None else family.alpha,
            "n": n,
            "seed": seed,
            "status": "ok",
            "path": str(instance_path),
            "generation_time_s": "",
            "reused": True,
            "error": "",
        }

    command = [
        str(native_bin),
        "instance",
        "generate",
        "--family",
        family.native_family,
        "--n",
        str(n),
        "--seed",
        str(seed),
        "--output-format",
        "circle",
        "--output",
        str(instance_path),
    ]
    if family.alpha is not None:
        command.extend(["--alpha", str(family.alpha)])
    start = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_s,
        )
        elapsed = time.perf_counter() - start
    except subprocess.TimeoutExpired as exc:
        return base_row(family, n, seed, instance_path, timeout_s, "timeout", str(exc))
    if completed.returncode != 0:
        return base_row(
            family,
            n,
            seed,
            instance_path,
            elapsed,
            "error",
            (completed.stderr or completed.stdout).strip(),
        )
    return {
        "family": family.slug,
        "label": family.label,
        "native_family": family.native_family,
        "alpha": "" if family.alpha is None else family.alpha,
        "n": n,
        "seed": seed,
        "status": "ok",
        "path": str(instance_path),
        "generation_time_s": elapsed,
        "reused": False,
        "error": "",
    }


def base_row(
    family: FamilyConfig,
    n: int,
    seed: int,
    instance_path: Path,
    elapsed: float,
    status: str,
    error: str,
) -> dict[str, object]:
    return {
        "family": family.slug,
        "label": family.label,
        "native_family": family.native_family,
        "alpha": "" if family.alpha is None else family.alpha,
        "n": n,
        "seed": seed,
        "status": status,
        "path": str(instance_path),
        "generation_time_s": elapsed,
        "generation_time_ms": 1000.0 * elapsed,
        "reused": False,
        "error": error,
    }


@dataclass(frozen=True)
class ParsedCircle:
    n: int
    m: int
    endpoint_order: list[int]


def parse_circle(path: Path) -> ParsedCircle:
    endpoint_order: list[int] = []
    in_order = False
    n = None
    m = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line == "c hord endpoint order START":
            in_order = True
            continue
        if line == "c hord endpoint order END":
            in_order = False
            continue
        if in_order:
            parts = line.split()
            if parts and parts[0] == "c":
                endpoint_order.extend(int(token) for token in parts[1:])
            continue
        parts = line.split()
        if len(parts) == 4 and parts[0] == "p":
            n = int(parts[2])
            m = int(parts[3])
    if n is None or m is None:
        raise ValueError(f"{path} does not contain a problem line")
    if len(endpoint_order) != 2 * n:
        raise ValueError(f"{path} has {len(endpoint_order)} endpoints for n={n}")
    return ParsedCircle(n=n, m=m, endpoint_order=endpoint_order)


def circle_degrees(endpoint_order: list[int], n: int) -> list[int]:
    left = [None] * (n + 1)
    right = [None] * (n + 1)
    for position, vertex in enumerate(endpoint_order):
        if left[vertex] is None:
            left[vertex] = position
        else:
            right[vertex] = position
    intervals = [(int(left[v]), int(right[v]), v) for v in range(1, n + 1)]
    intervals_by_right = sorted(intervals, key=lambda item: item[1])
    fenwick = Fenwick(len(endpoint_order) + 2)
    nested_inside = [0] * (n + 1)
    processed = 0
    for l_pos, _r_pos, vertex in intervals_by_right:
        nested_inside[vertex] = processed - fenwick.query(l_pos + 1)
        fenwick.add(l_pos + 1, 1)
        processed += 1
    degrees = [0] * n
    for l_pos, r_pos, vertex in intervals:
        endpoints_between = r_pos - l_pos - 1
        degrees[vertex - 1] = endpoints_between - 2 * nested_inside[vertex]
    return degrees


class Fenwick:
    def __init__(self, size: int) -> None:
        self.values = [0] * (size + 1)

    def add(self, index: int, delta: int) -> None:
        while index < len(self.values):
            self.values[index] += delta
            index += index & -index

    def query(self, index: int) -> int:
        total = 0
        while index > 0:
            total += self.values[index]
            index -= index & -index
        return total


def degree_summary(degrees: list[int]) -> dict[str, object]:
    ordered = sorted(degrees)
    return {
        "min_degree": ordered[0],
        "q1_degree": percentile(ordered, 0.25),
        "median_degree": percentile(ordered, 0.5),
        "q3_degree": percentile(ordered, 0.75),
        "max_degree": ordered[-1],
    }


def percentile(values: list[int], q: float) -> float:
    if not values:
        return math.nan
    index = q * (len(values) - 1)
    low = int(math.floor(index))
    high = int(math.ceil(index))
    if low == high:
        return float(values[low])
    weight = index - low
    return (1.0 - weight) * values[low] + weight * values[high]


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8", newline="") as infile:
        return list(csv.DictReader(infile))


def print_failure_summary(rows: list[dict[str, object]]) -> None:
    failures: dict[tuple[str, int], int] = {}
    attempts: dict[tuple[str, int], int] = {}
    for row in rows:
        key = (str(row["label"]), int(row["n"]))
        attempts[key] = attempts.get(key, 0) + 1
        if row.get("status") != "ok":
            failures[key] = failures.get(key, 0) + 1
    if not failures:
        print("generation failures: none", flush=True)
        return
    print("generation failures:", flush=True)
    for key in sorted(failures):
        label, n = key
        print(f"  {label}, n={n}: {failures[key]}/{attempts[key]} failed", flush=True)


def write_plots(rows: list[dict[str, object]], degree_rows: list[dict[str, object]], plot_root: Path) -> None:
    from eval.plot_style import apply_paper_style

    apply_paper_style()
    ok_rows = [row for row in rows if row.get("status") == "ok" and "average_degree" in row]
    timed_rows = [
        row
        for row in ok_rows
        if "generation_time_ms" in row and not parse_bool(row.get("reused", False))
    ]
    failed_labels = {str(row["label"]) for row in rows if row.get("status") != "ok"}

    sparse_labels = {"K4-Free", "Simple-YES", r"Density-YES ($\alpha=0$)"}
    sparse_box_labels = sparse_labels | {r"Density-YES ($\alpha=1/2$)"}
    density_labels = {
        r"Density-YES ($\alpha=0$)",
        r"Density-YES ($\alpha=1/2$)",
        r"Density-YES ($\alpha=1$)",
        r"Density-YES ($\alpha=2$)",
    }

    plot_average_degree_combined(ok_rows, plot_root / "average_degree_by_n.pdf", sparse_labels, density_labels)
    plot_quantile_metric_by_n(
        ok_rows,
        plot_root / "average_degree_by_n_sparse.pdf",
        "average_degree",
        "Average degree",
        include_labels=sparse_labels,
    )
    plot_quantile_metric_by_n(
        ok_rows,
        plot_root / "average_degree_by_n_density_yes.pdf",
        "average_degree",
        "Average degree",
        include_labels=density_labels,
    )

    plot_generation_time_combined(timed_rows, plot_root / "generation_time_by_n.pdf", failed_labels)
    plot_quantile_metric_by_n(
        timed_rows,
        plot_root / "generation_time_by_n_linear.pdf",
        "generation_time_ms",
        "Generation time (ms)",
        failed_labels=failed_labels,
    )
    plot_quantile_metric_by_n(
        timed_rows,
        plot_root / "generation_time_by_n_log.pdf",
        "generation_time_ms",
        "Generation time (ms)",
        yscale="log",
        failed_labels=failed_labels,
    )

    plot_degree_boxplots_combined(degree_rows, plot_root / "degree_boxplot_n2000.pdf", sparse_box_labels)
    plot_degree_boxplot(
        degree_rows,
        plot_root / "degree_boxplot_n2000_all.pdf",
        include_labels={family.label for family in FAMILIES},
    )
    plot_degree_boxplot(
        degree_rows,
        plot_root / "degree_boxplot_n2000_sparse.pdf",
        include_labels=sparse_box_labels,
    )


def parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() == "true"


def display_label(label: str, failed_labels: Optional[set[str]] = None) -> str:
    if failed_labels and label in failed_labels:
        return f"{label}$^*$"
    return label


def box_label(label: str) -> str:
    replacements = {
        "Simple-YES": "Simple\nYES",
        r"Density-YES ($\alpha=0$)": "D-YES\n$\\alpha=0$",
        r"Density-YES ($\alpha=1/2$)": "D-YES\n$\\alpha=1/2$",
        r"Density-YES ($\alpha=1$)": "D-YES\n$\\alpha=1$",
        r"Density-YES ($\alpha=2$)": "D-YES\n$\\alpha=2$",
    }
    return replacements.get(label, label)


def group_metric(rows: list[dict[str, object]], metric: str, label: str) -> dict[int, list[float]]:
    grouped: dict[int, list[float]] = {}
    for row in rows:
        if row["label"] != label or metric not in row:
            continue
        value = row[metric]
        if value == "":
            continue
        grouped.setdefault(int(row["n"]), []).append(float(value))
    return grouped


def plot_average_degree_combined(
    rows: list[dict[str, object]],
    path: Path,
    sparse_labels: set[str],
    density_labels: set[str],
) -> None:
    import matplotlib.pyplot as plt
    from eval.plot_style import figure_size, save_paper_figure

    fig, axes = plt.subplots(1, 2, figsize=figure_size("double"), sharex=True)
    plot_quantile_metric_on_axis(axes[0], rows, "average_degree", "Average degree", sparse_labels)
    axes[0].set_title("Sparse comparison")
    plot_quantile_metric_on_axis(axes[1], rows, "average_degree", "Average degree", density_labels)
    axes[1].set_title("Density-YES sweep")
    axes[1].set_ylabel("")
    save_paper_figure(fig, path)
    plt.close(fig)


def plot_generation_time_combined(
    rows: list[dict[str, object]],
    path: Path,
    failed_labels: set[str],
) -> None:
    import matplotlib.pyplot as plt
    from eval.plot_style import figure_size, save_paper_figure

    include_labels = {family.label for family in FAMILIES}
    fig, axes = plt.subplots(1, 2, figsize=figure_size("double"), sharex=True)
    plot_quantile_metric_on_axis(
        axes[0],
        rows,
        "generation_time_ms",
        "Generation time (ms)",
        include_labels,
        failed_labels=failed_labels,
    )
    axes[0].set_title("Linear scale")
    plot_quantile_metric_on_axis(
        axes[1],
        rows,
        "generation_time_ms",
        "Generation time (ms)",
        include_labels,
        yscale="log",
        failed_labels=failed_labels,
    )
    axes[1].set_title("Log scale")
    axes[1].set_ylabel("")
    save_paper_figure(fig, path)
    plt.close(fig)


def plot_quantile_metric_by_n(
    rows: list[dict[str, object]],
    path: Path,
    metric: str,
    ylabel: str,
    yscale: str = "linear",
    include_labels: Optional[set[str]] = None,
    failed_labels: Optional[set[str]] = None,
) -> None:
    import matplotlib.pyplot as plt
    from eval.plot_style import figure_size, save_paper_figure

    fig, ax = plt.subplots(figsize=figure_size("double"))
    plot_quantile_metric_on_axis(ax, rows, metric, ylabel, include_labels, yscale, failed_labels)
    save_paper_figure(fig, path)
    plt.close(fig)


def plot_quantile_metric_on_axis(
    ax,
    rows: list[dict[str, object]],
    metric: str,
    ylabel: str,
    include_labels: Optional[set[str]] = None,
    yscale: str = "linear",
    failed_labels: Optional[set[str]] = None,
) -> None:
    from matplotlib.ticker import NullFormatter
    from eval.plot_style import series_style

    all_xs: set[int] = set()
    for family in FAMILIES:
        if include_labels is not None and family.label not in include_labels:
            continue
        grouped = group_metric(rows, metric, family.label)
        if not grouped:
            continue
        xs = sorted(grouped)
        all_xs.update(xs)
        medians = [percentile(sorted(grouped[x]), 0.5) for x in xs]
        q1 = [percentile(sorted(grouped[x]), 0.25) for x in xs]
        q3 = [percentile(sorted(grouped[x]), 0.75) for x in xs]
        style = series_style(family.label)
        ax.plot(
            xs,
            medians,
            marker=style.marker,
            linestyle=style.linestyle,
            label=display_label(family.label, failed_labels),
            color=style.color,
        )
        ax.fill_between(xs, q1, q3, color=style.color, alpha=0.13, linewidth=0)
    ax.set_xlabel("$n$")
    ax.set_ylabel(ylabel)
    ax.set_xscale("log")
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_yscale(yscale)
    ax.grid(True, which="both")
    ax.legend(frameon=True)


def plot_degree_boxplots_combined(
    rows: list[dict[str, object]],
    path: Path,
    sparse_labels: set[str],
) -> None:
    import matplotlib.pyplot as plt
    from eval.plot_style import figure_size, save_paper_figure

    if not rows:
        return
    fig, axes = plt.subplots(1, 2, figsize=figure_size("double"))
    plot_degree_boxplot_on_axis(axes[0], rows, {family.label for family in FAMILIES})
    axes[0].set_title("All families")
    plot_degree_boxplot_on_axis(axes[1], rows, sparse_labels)
    axes[1].set_title("Sparse zoom")
    axes[1].set_ylabel("")
    save_paper_figure(fig, path)
    plt.close(fig)


def plot_degree_boxplot(
    rows: list[dict[str, object]],
    path: Path,
    include_labels: set[str],
) -> None:
    import matplotlib.pyplot as plt
    from eval.plot_style import figure_size, save_paper_figure

    if not rows:
        return
    fig, ax = plt.subplots(figsize=figure_size("double"))
    plot_degree_boxplot_on_axis(ax, rows, include_labels)
    save_paper_figure(fig, path)
    plt.close(fig)


def plot_degree_boxplot_on_axis(ax, rows: list[dict[str, object]], include_labels: set[str]) -> None:
    from eval.plot_style import series_style

    data: list[list[int]] = []
    labels: list[str] = []
    colors: list[str] = []
    for family in FAMILIES:
        if family.label not in include_labels:
            continue
        values = [int(row["degree"]) for row in rows if row["label"] == family.label]
        if not values:
            continue
        data.append(values)
        labels.append(box_label(family.label))
        colors.append(series_style(family.label).color)
    if not data:
        return
    box = ax.boxplot(data, patch_artist=True, showfliers=False, widths=0.6)
    for patch, color in zip(box["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.35)
        patch.set_edgecolor(color)
    for element in ("whiskers", "caps", "medians"):
        for artist in box[element]:
            artist.set_color("#333333")
            artist.set_linewidth(0.8)
    ax.set_xlabel("Family")
    ax.set_ylabel("Degree")
    ax.set_xticks(range(1, len(labels) + 1), labels, rotation=0)
    ax.grid(True, axis="y")


if __name__ == "__main__":
    raise SystemExit(main())
