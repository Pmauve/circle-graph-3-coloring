import argparse
import json
from pathlib import Path
import sys
from typing import Any, Iterable, Optional, TextIO

from three_col_circle_code.bench.env import collect_environment_metadata
from three_col_circle_code.bench.planning import (
    BenchmarkTrial,
    build_run_manifest,
    iter_benchmark_trials,
    load_spec_for_run,
    materialize_run_instances,
    prepare_run_directory,
    validate_run_environment,
)
from three_col_circle_code.bench.records import (
    build_benchmark_result_record,
    build_invalid_result_record,
    serialize_validation_errors,
)
from three_col_circle_code.bench.report import build_benchmark_report
from three_col_circle_code.bench.report_data import write_summary_csvs
from three_col_circle_code.bench.results import (
    DEFAULT_RUNS_ROOT,
    RESULTS_FILENAME,
    append_result,
    MANIFEST_FILENAME,
    write_manifest,
)
from three_col_circle_code.bench.specs import (
    canonical_params_json,
)
from three_col_circle_code.instances.io import load_instance
from three_col_circle_code.instances.model import InstanceFormatError, InstanceRecord
from three_col_circle_code.instances.validate import validate_instance
from three_col_circle_code.solvers.registry import run_solver


def run_benchmark(
    *,
    output_root: Path,
    spec_path: Path,
    progress_stream: TextIO | None = None,
) -> Path:
    """Run a resumable benchmark run from a JSON run spec."""
    spec_source, run_spec = load_spec_for_run(spec_path)
    spec_path = Path(spec_path)
    validate_run_environment(run_spec)
    run_dir = prepare_run_directory(
        output_root=output_root,
        spec_source=spec_source,
        run_id=spec_path.stem,
    )
    run_id_value = run_dir.name
    created_at = _load_existing_created_at(run_dir)

    _emit_progress(progress_stream, f"Starting benchmark run '{run_id_value}' from {spec_path}")
    _emit_progress(progress_stream, f"Run directory: {run_dir}")
    _emit_progress(progress_stream, f"Resolving {len(run_spec.instance_requests)} requested instances...")

    materialized = materialize_run_instances(
        run_spec,
        progress_callback=lambda message: _emit_progress(progress_stream, message),
    )
    trials = iter_benchmark_trials(run_spec, materialized.paths)
    _emit_progress(
        progress_stream,
        (
            f"Planned trials: {len(trials)} across {len(run_spec.instance_requests)} instances "
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
        build_run_manifest(
            run_id=run_id_value,
            run_spec=run_spec,
            created_at=created_at,
            environment=collect_environment_metadata(),
        ),
    )

    completed_trial_keys = _load_completed_trial_keys(run_dir)
    if completed_trial_keys:
        _emit_progress(
            progress_stream,
            f"Resuming existing run: skipping {len(completed_trial_keys)} completed trials",
        )

    cached_records: dict[Path, InstanceRecord] = {}
    cached_validations: dict[Path, tuple[bool, list[dict[str, Any]]]] = {}
    for index, trial in enumerate(trials, start=1):
        if trial.key in completed_trial_keys:
            continue
        _emit_progress(progress_stream, f"[{index}/{len(trials)}] {_format_trial(trial)}")
        loaded_record = cached_records.get(trial.instance_path)
        try:
            if loaded_record is None:
                loaded_record = load_instance(trial.instance_path)
                cached_records[trial.instance_path] = loaded_record
        except (InstanceFormatError, json.JSONDecodeError, OSError) as exc:
            result_row = _build_invalid_result_record(
                run_id=run_id_value,
                trial=trial,
                error=exc,
            )
            append_result(run_dir, result_row)
        else:
            validation_info = cached_validations.get(trial.instance_path)
            if validation_info is None:
                validation = validate_instance(loaded_record.graph, metadata=loaded_record.metadata.to_dict())
                validation_info = (
                    validation.ok,
                    serialize_validation_errors(validation.errors),
                )
                cached_validations[trial.instance_path] = validation_info
            result_row = _execute_benchmark_trial(
                run_dir=run_dir,
                run_id=run_id_value,
                trial=trial,
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


def _load_existing_created_at(run_dir: Path) -> Optional[str]:
    manifest_path = Path(run_dir) / MANIFEST_FILENAME
    if not manifest_path.exists():
        return None
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    created_at = payload.get("created_at")
    if created_at is None:
        return None
    return str(created_at)


def _load_completed_trial_keys(run_dir: Path) -> set[tuple[str, str, str]]:
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


def _execute_benchmark_trial(
    *,
    run_dir: Path,
    run_id: str,
    trial: BenchmarkTrial,
    record: Optional[InstanceRecord] = None,
    validation_ok: Optional[bool] = None,
    validation_errors: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    try:
        loaded_record = record or load_instance(trial.instance_path)
    except (InstanceFormatError, json.JSONDecodeError, OSError) as exc:
        result_row = _build_invalid_result_record(
            run_id=run_id,
            trial=trial,
            error=exc,
        )
        append_result(run_dir, result_row)
        return result_row

    if validation_ok is None or validation_errors is None:
        validation = validate_instance(loaded_record.graph, metadata=loaded_record.metadata.to_dict())
        validation_ok = validation.ok
        validation_errors = serialize_validation_errors(validation.errors)
    solve_result = run_solver(loaded_record, trial.solver_config)
    result_row = _build_result_record(
        run_id=run_id,
        trial=trial,
        record=loaded_record,
        validation_ok=validation_ok,
        validation_errors=validation_errors,
        solve_result=solve_result,
    )
    append_result(run_dir, result_row)
    return result_row


def _build_result_record(
    *,
    run_id: str,
    trial: BenchmarkTrial,
    record: InstanceRecord,
    validation_ok: bool,
    validation_errors: list[dict[str, Any]],
    solve_result: Any,
) -> dict[str, Any]:
    return build_benchmark_result_record(
        run_id=run_id,
        instance_path=trial.instance_path,
        record=record,
        solver_target=trial.solver_config.target,
        solver_params=dict(trial.solver_config.params),
        solver_label=trial.solver_config.label,
        validation_ok=validation_ok,
        validation_errors=validation_errors,
        solve_result=solve_result,
    )


def _build_invalid_result_record(
    *,
    run_id: str,
    trial: BenchmarkTrial,
    error: Exception,
) -> dict[str, Any]:
    return build_invalid_result_record(
        run_id=run_id,
        instance_id=trial.instance_path.stem,
        instance_path=trial.instance_path,
        family=trial.instance_request.family,
        n=trial.instance_request.n,
        seed=trial.instance_request.seed,
        solver_target=trial.solver_config.target,
        solver=trial.solver_config.solver,
        backend=trial.solver_config.backend,
        solver_params=dict(trial.solver_config.params),
        solver_label=trial.solver_config.label,
        error=error,
    )


def _emit_progress(progress_stream: TextIO | None, message: str) -> None:
    if progress_stream is None:
        return
    print(message, file=progress_stream, flush=True)


def _format_trial(trial: BenchmarkTrial) -> str:
    return (
        f"{trial.instance_request.instance_id} | "
        f"{trial.solver_config.target} | "
        f"params={trial.solver_config.params}"
    )


def _format_result_summary(result_row: dict[str, Any]) -> str:
    status = str(result_row["status"])
    wall_time_s = result_row.get("wall_time_s")
    error = result_row.get("error")
    if wall_time_s is not None:
        return f"{status} in {float(wall_time_s):.4f}s"
    if error:
        return f"{status}: {error}"
    return status


if __name__ == "__main__":
    raise SystemExit(main())
