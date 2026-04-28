import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean, median
from typing import Any, Mapping, Optional

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
    bucket: Optional[str]
    n: Optional[int]
    m: Optional[int]
    seed: Optional[int]
    source: Optional[str]
    solver_target: str
    solver: Optional[str]
    backend: Optional[str]
    solver_params: dict[str, Any]
    solver_label: Optional[str]
    status: str
    wall_time_s: Optional[float]
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
    median_wall_time_s: Optional[float]
    max_wall_time_s: Optional[float]


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
        bucket=_optional_str(row.get("bucket")),
        n=_optional_int(row.get("n")),
        m=_optional_int(row.get("m")),
        seed=_optional_int(row.get("seed")),
        source=_optional_str(row.get("source")),
        solver_target=str(row["solver_target"]),
        solver=_optional_str(row.get("solver")),
        backend=_optional_str(row.get("backend")),
        solver_params=dict(row.get("solver_params", {})),
        solver_label=_optional_str(row.get("solver_label")),
        status=str(row.get("status", "unknown")),
        wall_time_s=_optional_float(row.get("wall_time_s")),
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
                family=first_row.family,
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
        wall_times = [row.wall_time_s for row in target_rows if row.wall_time_s is not None]
        summary_rows.append(
            SolverSummaryRow(
                solver_target=solver_target,
                n_rows=len(target_rows),
                n_ok=statuses.get("ok", 0),
                n_error=statuses.get("error", 0),
                n_invalid=statuses.get("invalid", 0),
                median_wall_time_s=None if not wall_times else median(wall_times),
                max_wall_time_s=None if not wall_times else max(wall_times),
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
        "mean_wall_time_s",
        "median_wall_time_s",
        "max_wall_time_s",
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
    wall_times = [item.wall_time_s for item in rows if item.wall_time_s is not None]
    row.update(
        {
            "n_instances": len(rows),
            "n_ok": statuses.get("ok", 0),
            "n_error": statuses.get("error", 0),
            "n_invalid": statuses.get("invalid", 0),
            "mean_wall_time_s": None if not wall_times else mean(wall_times),
            "median_wall_time_s": None if not wall_times else median(wall_times),
            "max_wall_time_s": None if not wall_times else max(wall_times),
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
    if field == "solver_target":
        return solver_variant_label(row.solver_target, row.solver_params, row.solver_label)
    return getattr(row, field)


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
