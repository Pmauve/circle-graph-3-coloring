import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable, Mapping, Optional

from three_col_circle_code.bench.results import MANIFEST_FILENAME, RESULTS_FILENAME
from three_col_circle_code.bench.specs import canonical_params_json


SUMMARY_BY_N_FILENAME = "summary_by_n.csv"
SUMMARY_BY_BUCKET_FILENAME = "summary_by_bucket.csv"
SUMMARY_OVERALL_FILENAME = "summary_overall.csv"


@dataclass(frozen=True)
class ReportRunMetadata:
    run_id: str
    created_at: Optional[str]
    manifest_present: bool
    solver_targets: tuple[str, ...]
    n_instances: int
    n_tasks: int
    environment: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReportRow:
    instance_id: str
    instance_path: Optional[str]
    family: Optional[str]
    family_label: Optional[str]
    bucket: Optional[str]
    n: Optional[int]
    m: Optional[int]
    average_degree: Optional[float]
    num_colors: Optional[int]
    seed: Optional[int]
    source: Optional[str]
    solver_target: str
    solver: Optional[str]
    backend: Optional[str]
    solver_params: dict[str, Any]
    solver_label: Optional[str]
    status: str
    repetitions: int
    ok_repetitions: int
    mean_wall_time_s: Optional[float]
    median_wall_time_s: Optional[float]
    mean_total_native_time_s: Optional[float]
    median_total_native_time_s: Optional[float]
    mean_load_prepare_time_s: Optional[float]
    median_load_prepare_time_s: Optional[float]
    mean_solve_time_s: Optional[float]
    median_solve_time_s: Optional[float]
    mean_peak_rss_kb: Optional[float]
    median_peak_rss_kb: Optional[float]
    max_peak_rss_kb: Optional[float]
    measurement_wall_times: tuple[float, ...]
    measurement_total_native_times: tuple[float, ...]
    measurement_load_prepare_times: tuple[float, ...]
    measurement_solve_times: tuple[float, ...]
    measurement_peak_rss_kb: tuple[float, ...]
    is_colorable: Optional[bool]
    validation_ok: bool
    error: Optional[str]


@dataclass(frozen=True)
class AgreementRow:
    instance_id: str
    family: Optional[str]
    bucket: Optional[str]
    n: Optional[int]
    solver_targets: tuple[str, ...]
    statuses: tuple[tuple[str, str], ...]
    answers: tuple[tuple[str, Optional[bool]], ...]
    all_statuses_ok: bool
    unanimous_answer: Optional[bool]
    is_agreement: bool

    @property
    def statuses_summary(self) -> str:
        return ", ".join(f"{solver_target}={status}" for solver_target, status in self.statuses)

    @property
    def answers_summary(self) -> str:
        def _format(answer: Optional[bool]) -> str:
            if answer is None:
                return "unknown"
            return "yes" if answer else "no"

        return ", ".join(f"{solver_target}={_format(answer)}" for solver_target, answer in self.answers)


@dataclass(frozen=True)
class SolverSummaryRow:
    solver_target: str
    n_rows: int
    n_ok: int
    n_error: int
    n_invalid: int
    repetitions: int
    ok_repetitions: int
    mean_wall_time_s: Optional[float]
    median_wall_time_s: Optional[float]
    mean_total_native_time_s: Optional[float]
    median_total_native_time_s: Optional[float]
    mean_load_prepare_time_s: Optional[float]
    median_load_prepare_time_s: Optional[float]
    mean_solve_time_s: Optional[float]
    median_solve_time_s: Optional[float]
    mean_peak_rss_kb: Optional[float]
    median_peak_rss_kb: Optional[float]
    max_peak_rss_kb: Optional[float]


@dataclass(frozen=True)
class ReportHeadlineMetrics:
    total_rows: int
    total_instances: int
    n_solver_targets: int
    n_unanimous_agreements: int
    n_disagreements: int
    n_ok: int
    n_error: int
    n_invalid: int
    best_median_runtime_solver_target: Optional[str]


@dataclass(frozen=True)
class BenchmarkReportData:
    metadata: ReportRunMetadata
    rows: tuple[ReportRow, ...]
    agreement_rows: tuple[AgreementRow, ...]
    solver_summary_rows: tuple[SolverSummaryRow, ...]
    headline_metrics: ReportHeadlineMetrics

    @property
    def disagreement_rows(self) -> tuple[AgreementRow, ...]:
        return tuple(row for row in self.agreement_rows if not row.is_agreement)


def solver_variant_key(solver_target: str, solver_params: Mapping[str, Any]) -> str:
    """Build one stable identity key for a solver plus its parameters."""
    return f"{solver_target}|{canonical_params_json(dict(solver_params))}"


def solver_variant_label(
    solver_target: str,
    solver_params: Mapping[str, Any],
    solver_label: Optional[str] = None,
) -> str:
    """Build one stable display label for a solver plus its parameters."""
    if solver_label is not None:
        return solver_label
    params_json = canonical_params_json(dict(solver_params))
    if params_json == "{}":
        return solver_target
    params = json.loads(params_json)
    rendered_params = ", ".join(
        f"{name}={_render_solver_param_value(value)}"
        for name, value in params.items()
    )
    return f"{solver_target} [{rendered_params}]"


def load_benchmark_report_data(run_dir: Path) -> BenchmarkReportData:
    """Load one benchmark run directory into a normalized report model."""
    rows = _load_result_rows(run_dir)
    manifest = _load_manifest(run_dir)
    metadata = _build_run_metadata(run_dir, manifest, rows)
    agreement_rows = _build_agreement_rows(rows, metadata.solver_targets)
    solver_summary_rows = _build_solver_summary_rows(rows, metadata.solver_targets)
    headline_metrics = _build_headline_metrics(rows, agreement_rows, solver_summary_rows, metadata)
    return BenchmarkReportData(
        metadata=metadata,
        rows=rows,
        agreement_rows=agreement_rows,
        solver_summary_rows=solver_summary_rows,
        headline_metrics=headline_metrics,
    )


def write_summary_csvs(run_dir: Path) -> None:
    """Write the lightweight grouped summary CSVs for one benchmark run."""
    rows = _load_result_rows(run_dir)
    _write_summary_csv(
        run_dir / SUMMARY_BY_N_FILENAME,
        rows,
        group_fields=("family", "n", "solver_target"),
    )
    _write_summary_csv(
        run_dir / SUMMARY_BY_BUCKET_FILENAME,
        rows,
        group_fields=("family", "bucket", "solver_target"),
    )
    _write_summary_csv(
        run_dir / SUMMARY_OVERALL_FILENAME,
        rows,
        group_fields=("family", "solver_target"),
    )


def build_report_plot_payload(data: BenchmarkReportData) -> dict[str, Any]:
    """Build compact JSON data for the interactive report plots."""
    rows: list[dict[str, Any]] = []
    aggregate_inputs: list[tuple[ReportRow, str, str]] = []
    families: set[str] = set()
    solver_labels: set[str] = set()
    for row in data.rows:
        if row.n is None:
            continue
        family = _display_family(row) or "unknown"
        solver_label = solver_variant_label(row.solver_target, row.solver_params, row.solver_label)
        families.add(family)
        solver_labels.add(solver_label)
        aggregate_inputs.append((row, family, solver_label))
        rows.append(
            {
                "instance_id": row.instance_id,
                "family": family,
                "bucket": row.bucket,
                "n": row.n,
                "m": row.m,
                "average_degree": row.average_degree,
                "solver": solver_label,
                "solver_target": row.solver_target,
                "solver_params": row.solver_params,
                "status": row.status,
                "is_colorable": row.is_colorable,
                "metrics": {
                    "wall_time_s": row.mean_wall_time_s,
                    "native_total_time_s": row.mean_total_native_time_s,
                    "load_prepare_time_s": row.mean_load_prepare_time_s,
                    "solve_time_s": row.mean_solve_time_s,
                    "max_peak_rss_mb": None if row.max_peak_rss_kb is None else row.max_peak_rss_kb / 1024.0,
                },
            }
        )
    aggregates = _build_plot_aggregates(aggregate_inputs)
    return {
        "families": sorted(families),
        "solvers": sorted(solver_labels),
        "metrics": [
            {"key": "wall_time_s", "label": "Wall time", "y_axis": "mean_wall_time_s"},
            {"key": "native_total_time_s", "label": "Native total", "y_axis": "mean_total_native_time_s"},
            {"key": "load_prepare_time_s", "label": "Load + prepare", "y_axis": "mean_load_prepare_time_s"},
            {"key": "solve_time_s", "label": "Solve", "y_axis": "mean_solve_time_s"},
        ],
        "rows": rows,
        "aggregates": aggregates,
    }


def _load_manifest(run_dir: Path) -> Optional[dict[str, Any]]:
    manifest_path = Path(run_dir) / MANIFEST_FILENAME
    if not manifest_path.exists():
        return None
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _load_result_rows(run_dir: Path) -> tuple[ReportRow, ...]:
    results_path = Path(run_dir) / RESULTS_FILENAME
    if not results_path.exists():
        raise FileNotFoundError(f"benchmark run {run_dir} does not contain {RESULTS_FILENAME}")
    with results_path.open(encoding="utf-8") as infile:
        rows = [json.loads(line) for line in infile if line.strip()]
    normalized_rows = tuple(_normalize_report_row(row) for row in rows)
    return _dedupe_result_rows(normalized_rows)


def _dedupe_result_rows(rows: tuple[ReportRow, ...]) -> tuple[ReportRow, ...]:
    deduped: dict[tuple[str, str], ReportRow] = {}
    for row in rows:
        key = (row.instance_id, solver_variant_key(row.solver_target, row.solver_params))
        if key in deduped:
            # Keep the last occurrence to match the final recorded task result.
            deduped.pop(key)
        deduped[key] = row
    return tuple(deduped.values())


def _normalize_report_row(row: Mapping[str, Any]) -> ReportRow:
    return ReportRow(
        instance_id=str(row["instance_id"]),
        instance_path=_optional_str(row.get("instance_path")),
        family=_optional_str(row.get("family")),
        family_label=_optional_str(row.get("family_label")),
        bucket=_optional_str(row.get("bucket")),
        n=_optional_int(row.get("n")),
        m=_optional_int(row.get("m")),
        average_degree=_average_degree_from_row(row),
        num_colors=_optional_int(row.get("num_colors")),
        seed=_optional_int(row.get("seed")),
        source=_optional_str(row.get("source")),
        solver_target=str(row["solver_target"]),
        solver=_optional_str(row.get("solver")),
        backend=_optional_str(row.get("backend")),
        solver_params=dict(row.get("solver_params", {})),
        solver_label=_optional_str(row.get("solver_label")),
        status=str(row.get("status", "unknown")),
        repetitions=int(row.get("repetitions", 1)),
        ok_repetitions=int(row.get("ok_repetitions", 1 if row.get("status") == "ok" else 0)),
        mean_wall_time_s=_optional_float(row.get("mean_wall_time_s", row.get("wall_time_s"))),
        median_wall_time_s=_optional_float(row.get("median_wall_time_s", row.get("wall_time_s"))),
        mean_total_native_time_s=_optional_float(
            row.get("mean_total_native_time_s", row.get("mean_core_time_s", row.get("core_time_s")))
        ),
        median_total_native_time_s=_optional_float(
            row.get("median_total_native_time_s", row.get("median_core_time_s", row.get("core_time_s")))
        ),
        mean_load_prepare_time_s=_optional_float(row.get("mean_load_prepare_time_s", row.get("load_prepare_time_s"))),
        median_load_prepare_time_s=_optional_float(
            row.get("median_load_prepare_time_s", row.get("load_prepare_time_s"))
        ),
        mean_solve_time_s=_optional_float(row.get("mean_solve_time_s", row.get("solve_time_s"))),
        median_solve_time_s=_optional_float(row.get("median_solve_time_s", row.get("solve_time_s"))),
        mean_peak_rss_kb=_optional_float(row.get("mean_peak_rss_kb", row.get("peak_rss_kb"))),
        median_peak_rss_kb=_optional_float(row.get("median_peak_rss_kb", row.get("peak_rss_kb"))),
        max_peak_rss_kb=_optional_float(row.get("max_peak_rss_kb", row.get("peak_rss_kb"))),
        measurement_wall_times=_measurement_wall_times(row),
        measurement_total_native_times=_measurement_total_native_times(row),
        measurement_load_prepare_times=_measurement_float_values(
            row,
            measurement_field="load_prepare_time_s",
            mean_field="mean_load_prepare_time_s",
        ),
        measurement_solve_times=_measurement_float_values(
            row,
            measurement_field="solve_time_s",
            mean_field="mean_solve_time_s",
        ),
        measurement_peak_rss_kb=_measurement_peak_rss_kb(row),
        is_colorable=_optional_bool(row.get("is_colorable")),
        validation_ok=bool(row.get("validation_ok", False)),
        error=_optional_str(row.get("error")),
    )


def _build_run_metadata(
    run_dir: Path,
    manifest: Optional[Mapping[str, Any]],
    rows: tuple[ReportRow, ...],
) -> ReportRunMetadata:
    inferred_solver_targets = tuple(
        sorted(
            {
                solver_variant_label(row.solver_target, row.solver_params, row.solver_label)
                for row in rows
            }
        )
    )
    inferred_instance_count = len({row.instance_id for row in rows})
    if manifest is None:
        return ReportRunMetadata(
            run_id=run_dir.name,
            created_at=None,
            manifest_present=False,
            solver_targets=inferred_solver_targets,
            n_instances=inferred_instance_count,
            n_tasks=len(rows),
            environment={},
        )

    manifest_solver_targets = tuple(
        sorted(
            {
                solver_variant_label(
                    str(solver.get("target")),
                    dict(solver.get("params", {})),
                    _optional_str(solver.get("label")),
                )
                for solver in manifest.get("solvers", [])
                if solver.get("target") is not None
            }
        )
    )
    solver_targets = manifest_solver_targets or inferred_solver_targets
    return ReportRunMetadata(
        run_id=str(manifest.get("run_id", run_dir.name)),
        created_at=_optional_str(manifest.get("created_at")),
        manifest_present=True,
        solver_targets=solver_targets,
        n_instances=int(manifest.get("n_instances", inferred_instance_count)),
        n_tasks=int(manifest.get("n_tasks", len(rows))),
        environment=dict(manifest.get("environment", {})),
    )


def _build_agreement_rows(
    rows: tuple[ReportRow, ...],
    expected_solver_targets: tuple[str, ...],
) -> tuple[AgreementRow, ...]:
    grouped: dict[str, list[ReportRow]] = defaultdict(list)
    for row in rows:
        grouped[row.instance_id].append(row)

    agreement_rows: list[AgreementRow] = []
    expected_solver_target_set = set(expected_solver_targets)
    for instance_id in sorted(grouped):
        instance_rows = sorted(
            grouped[instance_id],
            key=lambda row: solver_variant_label(row.solver_target, row.solver_params, row.solver_label),
        )
        solver_targets = tuple(
            solver_variant_label(row.solver_target, row.solver_params, row.solver_label)
            for row in instance_rows
        )
        statuses = tuple(
            (
                solver_variant_label(row.solver_target, row.solver_params, row.solver_label),
                row.status,
            )
            for row in instance_rows
        )
        answers = tuple(
            (
                solver_variant_label(row.solver_target, row.solver_params, row.solver_label),
                row.is_colorable,
            )
            for row in instance_rows
        )
        status_values = {status for _, status in statuses}
        answer_values = {answer for _, answer in answers}
        has_complete_solver_set = (
            set(solver_targets) == expected_solver_target_set and len(solver_targets) == len(expected_solver_targets)
        )
        all_statuses_ok = has_complete_solver_set and status_values == {"ok"}
        unanimous_answer = None
        if has_complete_solver_set and len(answer_values) == 1 and None not in answer_values:
            unanimous_answer = next(iter(answer_values))
        is_agreement = all_statuses_ok and unanimous_answer is not None
        first_row = instance_rows[0]
        agreement_rows.append(
            AgreementRow(
                instance_id=instance_id,
                family=_display_family(first_row),
                bucket=first_row.bucket,
                n=first_row.n,
                solver_targets=solver_targets,
                statuses=statuses,
                answers=answers,
                all_statuses_ok=all_statuses_ok,
                unanimous_answer=unanimous_answer,
                is_agreement=is_agreement,
            )
        )
    return tuple(agreement_rows)


def _build_solver_summary_rows(
    rows: tuple[ReportRow, ...],
    solver_targets: tuple[str, ...],
) -> tuple[SolverSummaryRow, ...]:
    grouped: dict[str, list[ReportRow]] = defaultdict(list)
    for row in rows:
        grouped[solver_variant_label(row.solver_target, row.solver_params, row.solver_label)].append(row)

    summary_rows: list[SolverSummaryRow] = []
    for solver_target in solver_targets:
        target_rows = grouped.get(solver_target, [])
        statuses = Counter(row.status for row in target_rows)
        wall_times = [
            wall_time
            for row in target_rows
            for wall_time in row.measurement_wall_times
        ]
        total_native_times = [
            total_native_time
            for row in target_rows
            for total_native_time in row.measurement_total_native_times
        ]
        load_prepare_times = [
            load_prepare_time
            for row in target_rows
            for load_prepare_time in row.measurement_load_prepare_times
        ]
        solve_times = [
            solve_time
            for row in target_rows
            for solve_time in row.measurement_solve_times
        ]
        peak_rss_values = [
            peak_rss_kb
            for row in target_rows
            for peak_rss_kb in row.measurement_peak_rss_kb
        ]
        summary_rows.append(
            SolverSummaryRow(
                solver_target=solver_target,
                n_rows=len(target_rows),
                n_ok=statuses.get("ok", 0),
                n_error=statuses.get("error", 0),
                n_invalid=statuses.get("invalid", 0),
                repetitions=sum(row.repetitions for row in target_rows),
                ok_repetitions=sum(row.ok_repetitions for row in target_rows),
                mean_wall_time_s=None if not wall_times else mean(wall_times),
                median_wall_time_s=None if not wall_times else median(wall_times),
                mean_total_native_time_s=None if not total_native_times else mean(total_native_times),
                median_total_native_time_s=None if not total_native_times else median(total_native_times),
                mean_load_prepare_time_s=None if not load_prepare_times else mean(load_prepare_times),
                median_load_prepare_time_s=None if not load_prepare_times else median(load_prepare_times),
                mean_solve_time_s=None if not solve_times else mean(solve_times),
                median_solve_time_s=None if not solve_times else median(solve_times),
                mean_peak_rss_kb=None if not peak_rss_values else mean(peak_rss_values),
                median_peak_rss_kb=None if not peak_rss_values else median(peak_rss_values),
                max_peak_rss_kb=None if not peak_rss_values else max(peak_rss_values),
            )
        )
    return tuple(summary_rows)


def _build_headline_metrics(
    rows: tuple[ReportRow, ...],
    agreement_rows: tuple[AgreementRow, ...],
    solver_summary_rows: tuple[SolverSummaryRow, ...],
    metadata: ReportRunMetadata,
) -> ReportHeadlineMetrics:
    statuses = Counter(row.status for row in rows)
    best_runtime_row = min(
        (row for row in solver_summary_rows if row.median_wall_time_s is not None),
        key=lambda row: row.median_wall_time_s,
        default=None,
    )
    return ReportHeadlineMetrics(
        total_rows=len(rows),
        total_instances=len(agreement_rows),
        n_solver_targets=len(metadata.solver_targets),
        n_unanimous_agreements=sum(1 for row in agreement_rows if row.is_agreement),
        n_disagreements=sum(1 for row in agreement_rows if not row.is_agreement),
        n_ok=statuses.get("ok", 0),
        n_error=statuses.get("error", 0),
        n_invalid=statuses.get("invalid", 0),
        best_median_runtime_solver_target=(
            None if best_runtime_row is None else best_runtime_row.solver_target
        ),
    )


def _build_plot_aggregates(rows: list[tuple[ReportRow, str, str]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int, str], list[ReportRow]] = defaultdict(list)
    for row, family, solver_label in rows:
        if row.n is None:
            continue
        grouped[(family, row.n, solver_label)].append(row)

    aggregates: list[dict[str, Any]] = []
    for (family, n_value, solver_label), group_rows in sorted(grouped.items(), key=lambda item: item[0]):
        statuses = Counter(row.status for row in group_rows)
        ok_rows = [row for row in group_rows if row.status == "ok"]
        aggregates.append(
            {
                "family": family,
                "n": n_value,
                "solver": solver_label,
                "n_rows": len(group_rows),
                "n_ok": statuses.get("ok", 0),
                "n_error": statuses.get("error", 0),
                "n_invalid": statuses.get("invalid", 0),
                "metrics": {
                    "wall_time_s": _aggregate_values(
                        row.mean_wall_time_s
                        for row in ok_rows
                    ),
                    "native_total_time_s": _aggregate_values(
                        row.mean_total_native_time_s
                        for row in ok_rows
                    ),
                    "load_prepare_time_s": _aggregate_values(
                        row.mean_load_prepare_time_s
                        for row in ok_rows
                    ),
                    "solve_time_s": _aggregate_values(
                        row.mean_solve_time_s
                        for row in ok_rows
                    ),
                    "max_peak_rss_mb": _aggregate_values(
                        None if row.max_peak_rss_kb is None else row.max_peak_rss_kb / 1024.0
                        for row in ok_rows
                    ),
                },
            }
        )
    return aggregates


def _aggregate_values(values: Iterable[Optional[float]]) -> Optional[dict[str, float | int]]:
    sorted_values = sorted(value for value in values if value is not None)
    if not sorted_values:
        return None
    return {
        "count": len(sorted_values),
        "median": median(sorted_values),
        "q25": _quantile(sorted_values, 0.25),
        "q75": _quantile(sorted_values, 0.75),
        "min": sorted_values[0],
        "max": sorted_values[-1],
    }


def _quantile(sorted_values: list[float], probability: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = probability * (len(sorted_values) - 1)
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    fraction = position - lower_index
    return sorted_values[lower_index] + fraction * (sorted_values[upper_index] - sorted_values[lower_index])


def _write_summary_csv(
    path: Path,
    rows: tuple[ReportRow, ...],
    *,
    group_fields: tuple[str, ...],
) -> None:
    grouped: dict[tuple[Any, ...], list[ReportRow]] = defaultdict(list)
    for row in rows:
        grouped[tuple(_summary_group_value(row, field) for field in group_fields)].append(row)

    fieldnames = list(group_fields) + [
        "n_instances",
        "n_ok",
        "n_error",
        "n_invalid",
        "repetitions",
        "ok_repetitions",
        "mean_average_degree",
        "mean_wall_time_s",
        "median_wall_time_s",
        "mean_total_native_time_s",
        "median_total_native_time_s",
        "mean_load_prepare_time_s",
        "median_load_prepare_time_s",
        "mean_solve_time_s",
        "median_solve_time_s",
        "mean_peak_rss_kb",
        "median_peak_rss_kb",
        "max_peak_rss_kb",
    ]
    with Path(path).open("w", encoding="utf-8", newline="") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        for group_key in sorted(grouped, key=_group_sort_key):
            writer.writerow(_build_summary_row(group_fields, group_key, grouped[group_key]))


def _build_summary_row(
    group_fields: tuple[str, ...],
    group_key: tuple[Any, ...],
    rows: list[ReportRow],
) -> dict[str, Any]:
    row = {field: value for field, value in zip(group_fields, group_key)}
    statuses = Counter(item.status for item in rows)
    wall_times = [
        wall_time
        for item in rows
        for wall_time in item.measurement_wall_times
    ]
    total_native_times = [
        total_native_time
        for item in rows
        for total_native_time in item.measurement_total_native_times
    ]
    load_prepare_times = [
        load_prepare_time
        for item in rows
        for load_prepare_time in item.measurement_load_prepare_times
    ]
    solve_times = [
        solve_time
        for item in rows
        for solve_time in item.measurement_solve_times
    ]
    peak_rss_values = [
        peak_rss_kb
        for item in rows
        for peak_rss_kb in item.measurement_peak_rss_kb
    ]
    average_degrees = [
        item.average_degree
        for item in rows
        if item.average_degree is not None
    ]
    row.update(
        {
            "n_instances": len(rows),
            "n_ok": statuses.get("ok", 0),
            "n_error": statuses.get("error", 0),
            "n_invalid": statuses.get("invalid", 0),
            "repetitions": sum(item.repetitions for item in rows),
            "ok_repetitions": sum(item.ok_repetitions for item in rows),
            "mean_average_degree": None if not average_degrees else mean(average_degrees),
            "mean_wall_time_s": None if not wall_times else mean(wall_times),
            "median_wall_time_s": None if not wall_times else median(wall_times),
            "mean_total_native_time_s": None if not total_native_times else mean(total_native_times),
            "median_total_native_time_s": None if not total_native_times else median(total_native_times),
            "mean_load_prepare_time_s": None if not load_prepare_times else mean(load_prepare_times),
            "median_load_prepare_time_s": None if not load_prepare_times else median(load_prepare_times),
            "mean_solve_time_s": None if not solve_times else mean(solve_times),
            "median_solve_time_s": None if not solve_times else median(solve_times),
            "mean_peak_rss_kb": None if not peak_rss_values else mean(peak_rss_values),
            "median_peak_rss_kb": None if not peak_rss_values else median(peak_rss_values),
            "max_peak_rss_kb": None if not peak_rss_values else max(peak_rss_values),
        }
    )
    return row


def _group_sort_key(group_key: tuple[Any, ...]) -> tuple[Any, ...]:
    return tuple(_sort_value(value) for value in group_key)


def _sort_value(value: Any) -> tuple[int, Any]:
    if value is None:
        return (1, "")
    return (0, value)


def _summary_group_value(row: ReportRow, field: str) -> Any:
    if field == "family":
        return _display_family(row)
    if field == "solver_target":
        return solver_variant_label(row.solver_target, row.solver_params, row.solver_label)
    return getattr(row, field)


def _display_family(row: ReportRow) -> Optional[str]:
    return row.family_label or row.family


def _render_solver_param_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True)


def _optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    return int(value)


def _optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    return float(value)


def _optional_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    return bool(value)


def _average_degree_from_row(row: Mapping[str, Any]) -> Optional[float]:
    explicit = row.get("average_degree")
    if explicit is not None:
        return float(explicit)
    n_vertices = row.get("n")
    n_edges = row.get("m")
    if n_vertices is None or n_edges is None:
        return None
    n_value = int(n_vertices)
    if n_value == 0:
        return 0.0
    return 2.0 * int(n_edges) / n_value


def _measurement_wall_times(row: Mapping[str, Any]) -> tuple[float, ...]:
    measurements = row.get("measurements")
    if isinstance(measurements, list):
        return tuple(
            float(item["wall_time_s"])
            for item in measurements
            if isinstance(item, Mapping)
            and item.get("status") == "ok"
            and item.get("wall_time_s") is not None
        )
    mean_wall_time_s = row.get("mean_wall_time_s")
    if mean_wall_time_s is not None:
        repetitions = int(row.get("ok_repetitions", row.get("repetitions", 1)))
        return tuple(float(mean_wall_time_s) for _ in range(repetitions))
    legacy_wall_time_s = row.get("wall_time_s")
    if legacy_wall_time_s is not None:
        return (float(legacy_wall_time_s),)
    return ()


def _measurement_total_native_times(row: Mapping[str, Any]) -> tuple[float, ...]:
    values = _measurement_float_values(
        row,
        measurement_field="total_native_time_s",
        mean_field="mean_total_native_time_s",
    )
    if values:
        return values
    legacy_mean = row.get("mean_core_time_s")
    if legacy_mean is not None:
        repetitions = int(row.get("ok_repetitions", row.get("repetitions", 1)))
        return tuple(float(legacy_mean) for _ in range(repetitions))
    legacy_core_time_s = row.get("core_time_s")
    if legacy_core_time_s is not None:
        return (float(legacy_core_time_s),)
    return ()


def _measurement_float_values(
    row: Mapping[str, Any],
    *,
    measurement_field: str,
    mean_field: str,
) -> tuple[float, ...]:
    measurements = row.get("measurements")
    if isinstance(measurements, list):
        return tuple(
            float(item[measurement_field])
            for item in measurements
            if isinstance(item, Mapping)
            and item.get("status") == "ok"
            and item.get(measurement_field) is not None
        )
    mean_value = row.get(mean_field)
    if mean_value is not None:
        repetitions = int(row.get("ok_repetitions", row.get("repetitions", 1)))
        return tuple(float(mean_value) for _ in range(repetitions))
    legacy_value = row.get(measurement_field)
    if legacy_value is not None:
        return (float(legacy_value),)
    return ()


def _measurement_peak_rss_kb(row: Mapping[str, Any]) -> tuple[float, ...]:
    measurements = row.get("measurements")
    if isinstance(measurements, list):
        return tuple(
            float(item["peak_rss_kb"])
            for item in measurements
            if isinstance(item, Mapping)
            and item.get("status") == "ok"
            and item.get("peak_rss_kb") is not None
        )
    mean_peak_rss_kb = row.get("mean_peak_rss_kb")
    if mean_peak_rss_kb is not None:
        repetitions = int(row.get("ok_repetitions", row.get("repetitions", 1)))
        return tuple(float(mean_peak_rss_kb) for _ in range(repetitions))
    legacy_peak_rss_kb = row.get("peak_rss_kb")
    if legacy_peak_rss_kb is not None:
        return (float(legacy_peak_rss_kb),)
    return ()
