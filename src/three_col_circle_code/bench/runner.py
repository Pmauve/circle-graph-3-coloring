import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
import platform
from pathlib import Path
import sys
from typing import Any, Iterable, Optional, TextIO

from three_col_circle_code.bench.env import collect_environment_metadata
from three_col_circle_code.bench.report import build_benchmark_report
from three_col_circle_code.bench.report_data import write_summary_csvs
from three_col_circle_code.bench.results import (
    DEFAULT_RUNS_ROOT,
    RESULTS_FILENAME,
    append_result,
    MANIFEST_FILENAME,
    normalize_run_label,
    write_manifest,
)
from three_col_circle_code.bench.specs import (
    InstanceRequest,
    RunSpec,
    canonical_params_json,
    load_run_spec,
)
from three_col_circle_code.generation.random_instances import generate_instance, write_instance
from three_col_circle_code.instances.io import load_instance
from three_col_circle_code.instances.model import InstanceFormatError, InstanceRecord, bucket_for_n
from three_col_circle_code.instances.validate import validate_instance
from three_col_circle_code.solvers.common import SolverConfig
from three_col_circle_code.solvers.registry import run_solver
from three_col_circle_code.solvers.sat import PYSAT_KISSAT404, SAT_BASELINE_SOLVER

BENCH_STATUS_INVALID = "invalid"
RUN_SPEC_FILENAME = "spec.json"


@dataclass(frozen=True)
class BenchmarkTask:
    instance_request: InstanceRequest
    instance_path: Path
    solver_config: SolverConfig

    @property
    def key(self) -> tuple[str, str, str]:
        return (
            self.instance_request.instance_id,
            self.solver_config.target,
            canonical_params_json(self.solver_config.params),
        )


@dataclass(frozen=True)
class MaterializedInstances:
    paths: dict[str, Path]
    n_found_flat: int
    n_found_nested: int
    n_generated: int


def run_benchmark(
    *,
    output_root: Path,
    spec_path: Path,
    progress_stream: TextIO | None = None,
) -> Path:
    """Run a resumable benchmark run from a JSON run spec."""
    spec_source, run_spec = load_run_spec(spec_path)
    spec_path = Path(spec_path)
    _validate_run_environment(run_spec)
    run_dir = _prepare_run_directory(
        output_root=output_root,
        spec_source=spec_source,
        run_id=spec_path.stem,
    )
    run_id_value = run_dir.name
    created_at = _load_existing_created_at(run_dir)

    _emit_progress(progress_stream, f"Starting benchmark run '{run_id_value}' from {spec_path}")
    _emit_progress(progress_stream, f"Run directory: {run_dir}")
    _emit_progress(progress_stream, f"Resolving {len(run_spec.instance_requests)} requested instances...")

    materialized = _materialize_run_instances(
        run_spec,
        progress_stream=progress_stream,
    )
    tasks = _iter_benchmark_tasks(run_spec, materialized.paths)
    _emit_progress(
        progress_stream,
        (
            f"Planned tasks: {len(tasks)} across {len(run_spec.instance_requests)} instances "
            f"and {len(run_spec.solver_configs)} solver configs"
        ),
    )
    _emit_progress(
        progress_stream,
        (
            "Instance pool: "
            f"{materialized.n_found_flat} flat, "
            f"{materialized.n_found_nested} nested, "
            f"{materialized.n_generated} generated"
        ),
    )

    write_manifest(
        run_dir,
        _build_manifest(
            run_id=run_id_value,
            run_spec=run_spec,
            created_at=created_at,
        ),
    )

    completed_task_keys = _load_completed_task_keys(run_dir)
    if completed_task_keys:
        _emit_progress(
            progress_stream,
            f"Resuming existing run: skipping {len(completed_task_keys)} completed tasks",
        )

    cached_records: dict[Path, InstanceRecord] = {}
    cached_validations: dict[Path, tuple[bool, list[dict[str, Any]]]] = {}
    for index, task in enumerate(tasks, start=1):
        if task.key in completed_task_keys:
            continue
        _emit_progress(progress_stream, f"[{index}/{len(tasks)}] {_format_task(task)}")
        loaded_record = cached_records.get(task.instance_path)
        try:
            if loaded_record is None:
                loaded_record = load_instance(task.instance_path)
                cached_records[task.instance_path] = loaded_record
        except (InstanceFormatError, json.JSONDecodeError, OSError) as exc:
            result_row = _build_invalid_result_record(
                run_id=run_id_value,
                task=task,
                error=exc,
            )
            append_result(run_dir, result_row)
        else:
            validation_info = cached_validations.get(task.instance_path)
            if validation_info is None:
                validation = validate_instance(loaded_record.graph, metadata=loaded_record.metadata.to_dict())
                validation_info = (
                    validation.ok,
                    _serialize_validation_errors(validation.errors),
                )
                cached_validations[task.instance_path] = validation_info
            result_row = _execute_benchmark_task(
                run_dir=run_dir,
                run_id=run_id_value,
                task=task,
                record=loaded_record,
                validation_ok=validation_info[0],
                validation_errors=validation_info[1],
            )
        _emit_progress(progress_stream, f"  -> {_format_result_summary(result_row)}")

    write_summary_csvs(run_dir)
    report_path = build_benchmark_report(run_dir)
    status_counts = _load_status_counts(run_dir)
    _emit_progress(
        progress_stream,
        (
            f"Completed run '{run_id_value}': "
            f"ok={status_counts.get('ok', 0)}, "
            f"error={status_counts.get('error', 0)}, "
            f"invalid={status_counts.get('invalid', 0)}"
        ),
    )
    _emit_progress(progress_stream, f"Results: {run_dir / RESULTS_FILENAME}")
    _emit_progress(progress_stream, f"Manifest: {run_dir / MANIFEST_FILENAME}")
    _emit_progress(progress_stream, f"Report: {report_path}")
    return run_dir


def main(argv: Optional[Iterable[str]] = None) -> int:
    """Run benchmark solvers from a benchmark run spec."""
    parser = argparse.ArgumentParser(description="Run benchmark solvers from a benchmark run spec.")
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_RUNS_ROOT)
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        run_dir = run_benchmark(
            output_root=args.output_root,
            spec_path=args.spec,
            progress_stream=sys.stderr,
        )
    except ValueError as exc:
        print(f"benchmark run failed: {exc}", file=sys.stderr)
        return 2
    print(run_dir)
    return 0


def _prepare_run_directory(
    *,
    output_root: Path,
    spec_source: str,
    run_id: str,
) -> Path:
    run_dir = Path(output_root) / normalize_run_label(run_id)
    if run_dir.exists():
        if not run_dir.is_dir():
            raise ValueError(f"run path {run_dir} exists but is not a directory")
    else:
        run_dir.mkdir(parents=True, exist_ok=False)

    spec_copy_path = run_dir / RUN_SPEC_FILENAME
    if spec_copy_path.exists():
        existing_source = spec_copy_path.read_text(encoding="utf-8")
        if existing_source != spec_source:
            raise ValueError("existing run_id refers to a run directory with a different benchmark spec")
    else:
        spec_copy_path.write_text(spec_source, encoding="utf-8")
    return run_dir


def _load_existing_created_at(run_dir: Path) -> Optional[str]:
    manifest_path = Path(run_dir) / MANIFEST_FILENAME
    if not manifest_path.exists():
        return None
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    created_at = payload.get("created_at")
    if created_at is None:
        return None
    return str(created_at)


def _materialize_run_instances(
    run_spec: RunSpec,
    *,
    progress_stream: TextIO | None = None,
) -> MaterializedInstances:
    resolved: dict[str, Path] = {}
    n_found_flat = 0
    n_found_nested = 0
    n_generated = 0
    missing_requests = [
        request
        for request in run_spec.instance_requests
        if _resolve_existing_instance_path(
            instance_pool_root=run_spec.instance_pool_root,
            request=request,
        )[0] is None
    ]
    if missing_requests:
        _emit_progress(
            progress_stream,
            f"Generating missing instances ({len(missing_requests)} total)...",
        )
    for request in run_spec.instance_requests:
        instance_path, resolution = _resolve_or_generate_instance(
            instance_pool_root=run_spec.instance_pool_root,
            request=request,
        )
        resolved[request.instance_id] = instance_path
        if resolution == "flat":
            n_found_flat += 1
        elif resolution == "nested":
            n_found_nested += 1
        else:
            n_generated += 1
            if _should_emit_generation_progress(
                generated_count=n_generated,
                generated_total=len(missing_requests),
            ):
                _emit_progress(
                    progress_stream,
                    f"Generated {n_generated}/{len(missing_requests)} missing instances",
                )
    return MaterializedInstances(
        paths=resolved,
        n_found_flat=n_found_flat,
        n_found_nested=n_found_nested,
        n_generated=n_generated,
    )


def _resolve_or_generate_instance(
    *,
    instance_pool_root: Path,
    request: InstanceRequest,
) -> tuple[Path, str]:
    existing_instance_path, existing_resolution = _resolve_existing_instance_path(
        instance_pool_root=instance_pool_root,
        request=request,
    )
    if existing_instance_path is not None and existing_resolution is not None:
        return existing_instance_path, existing_resolution

    record = generate_instance(family=request.family, n=request.n, seed=request.seed)
    return write_instance(record, instance_pool_root), "generated"


def _resolve_existing_instance_path(
    *,
    instance_pool_root: Path,
    request: InstanceRequest,
) -> tuple[Optional[Path], Optional[str]]:
    flat_instance_path = Path(instance_pool_root) / f"{request.instance_id}.json"
    if flat_instance_path.exists():
        return flat_instance_path, "flat"

    nested_instance_path = (
        Path(instance_pool_root)
        / request.family
        / bucket_for_n(request.n)
        / f"{request.instance_id}.json"
    )
    if nested_instance_path.exists():
        return nested_instance_path, "nested"
    return None, None


def _iter_benchmark_tasks(
    run_spec: RunSpec,
    instance_paths: dict[str, Path],
) -> tuple[BenchmarkTask, ...]:
    tasks = [
        BenchmarkTask(
            instance_request=request,
            instance_path=instance_paths[request.instance_id],
            solver_config=solver_config,
        )
        for request in run_spec.instance_requests
        for solver_config in run_spec.solver_configs
    ]
    return tuple(
        sorted(
            tasks,
            key=lambda task: (
                task.instance_request.family,
                task.instance_request.n,
                task.instance_request.seed,
                task.solver_config.target,
                canonical_params_json(task.solver_config.params),
            ),
        )
    )


def _load_completed_task_keys(run_dir: Path) -> set[tuple[str, str, str]]:
    results_path = Path(run_dir) / RESULTS_FILENAME
    if not results_path.exists():
        return set()

    completed: set[tuple[str, str, str]] = set()
    with results_path.open(encoding="utf-8") as infile:
        for line in infile:
            if not line.strip():
                continue
            row = json.loads(line)
            completed.add(
                (
                    str(row["instance_id"]),
                    str(row["solver_target"]),
                    canonical_params_json(row.get("solver_params", {})),
                )
            )
    return completed


def _load_status_counts(run_dir: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    results_path = Path(run_dir) / RESULTS_FILENAME
    if not results_path.exists():
        return counts
    with results_path.open(encoding="utf-8") as infile:
        for line in infile:
            if not line.strip():
                continue
            row = json.loads(line)
            status = str(row["status"])
            counts[status] = counts.get(status, 0) + 1
    return counts


def _execute_benchmark_task(
    *,
    run_dir: Path,
    run_id: str,
    task: BenchmarkTask,
    record: Optional[InstanceRecord] = None,
    validation_ok: Optional[bool] = None,
    validation_errors: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    try:
        loaded_record = record or load_instance(task.instance_path)
    except (InstanceFormatError, json.JSONDecodeError, OSError) as exc:
        result_row = _build_invalid_result_record(
            run_id=run_id,
            task=task,
            error=exc,
        )
        append_result(run_dir, result_row)
        return result_row

    if validation_ok is None or validation_errors is None:
        validation = validate_instance(loaded_record.graph, metadata=loaded_record.metadata.to_dict())
        validation_ok = validation.ok
        validation_errors = _serialize_validation_errors(validation.errors)
    solve_result = run_solver(loaded_record, task.solver_config)
    result_row = _build_result_record(
        run_id=run_id,
        task=task,
        record=loaded_record,
        validation_ok=validation_ok,
        validation_errors=validation_errors,
        solve_result=solve_result,
    )
    append_result(run_dir, result_row)
    return result_row


def _build_manifest(
    *,
    run_id: str,
    run_spec: RunSpec,
    created_at: Optional[str],
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "created_at": created_at or datetime.now(UTC).isoformat(),
        "spec_filename": RUN_SPEC_FILENAME,
        "instance_pool_root": str(run_spec.instance_pool_root),
        "instance_requests": [
            {
                "instance_id": request.instance_id,
                "family": request.family,
                "n": request.n,
                "seed": request.seed,
            }
            for request in run_spec.instance_requests
        ],
        "solvers": [
            {
                "solver": config.solver,
                "backend": config.backend,
                "target": config.target,
                "params": dict(config.params),
            }
            for config in run_spec.solver_configs
        ],
        "n_instances": len(run_spec.instance_requests),
        "n_tasks": len(run_spec.instance_requests) * len(run_spec.solver_configs),
        "environment": collect_environment_metadata(),
    }


def _build_result_record(
    *,
    run_id: str,
    task: BenchmarkTask,
    record: InstanceRecord,
    validation_ok: bool,
    validation_errors: list[dict[str, Any]],
    solve_result: Any,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "instance_id": record.metadata.instance_id,
        "instance_path": str(task.instance_path),
        "family": record.metadata.family,
        "bucket": record.metadata.bucket,
        "n": record.metadata.n,
        "m": record.metadata.m,
        "seed": record.metadata.seed,
        "source": record.metadata.source,
        "solver_target": task.solver_config.target,
        "solver": solve_result.solver,
        "backend": solve_result.backend,
        "solver_params": dict(task.solver_config.params),
        "status": solve_result.status,
        "wall_time_s": solve_result.wall_time_s,
        "is_colorable": solve_result.is_colorable,
        "validation_ok": validation_ok,
        "validation_errors": validation_errors,
        "details": solve_result.details,
        "error": solve_result.error,
    }


def _build_invalid_result_record(
    *,
    run_id: str,
    task: BenchmarkTask,
    error: Exception,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "instance_id": task.instance_path.stem,
        "instance_path": str(task.instance_path),
        "family": task.instance_request.family,
        "bucket": None,
        "n": task.instance_request.n,
        "m": None,
        "seed": task.instance_request.seed,
        "source": None,
        "solver_target": task.solver_config.target,
        "solver": task.solver_config.solver,
        "backend": task.solver_config.backend,
        "solver_params": dict(task.solver_config.params),
        "status": BENCH_STATUS_INVALID,
        "wall_time_s": None,
        "is_colorable": None,
        "validation_ok": False,
        "validation_errors": [
            {
                "code": "instance.load_error",
                "message": str(error),
            }
        ],
        "details": {"load_error_type": type(error).__name__},
        "error": str(error),
    }


def _serialize_validation_errors(errors: Iterable[Any]) -> list[dict[str, Any]]:
    return [{"code": issue.code, "message": issue.message} for issue in errors]


def _validate_run_environment(run_spec: RunSpec) -> None:
    system_name = platform.system()
    for solver_config in run_spec.solver_configs:
        if (
            system_name == "Windows"
            and solver_config.solver == SAT_BASELINE_SOLVER
            and solver_config.backend == PYSAT_KISSAT404
        ):
            raise ValueError(
                "SAT backend 'pysat-kissat404' is not supported on Windows; "
                "use WSL/Linux or remove it from the run spec"
            )


def _emit_progress(progress_stream: TextIO | None, message: str) -> None:
    if progress_stream is None:
        return
    print(message, file=progress_stream, flush=True)


def _format_task(task: BenchmarkTask) -> str:
    return f"{task.instance_request.instance_id} | {task.solver_config.target} | params={task.solver_config.params}"


def _format_result_summary(result_row: dict[str, Any]) -> str:
    status = str(result_row["status"])
    wall_time_s = result_row.get("wall_time_s")
    error = result_row.get("error")
    if wall_time_s is not None:
        return f"{status} in {float(wall_time_s):.4f}s"
    if error:
        return f"{status}: {error}"
    return status


def _should_emit_generation_progress(*, generated_count: int, generated_total: int) -> bool:
    if generated_total < 1:
        return False
    return generated_count in {1, generated_total} or generated_count % 10 == 0


if __name__ == "__main__":
    raise SystemExit(main())
