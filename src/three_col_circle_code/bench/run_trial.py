import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, median
import sys
from typing import Any, Iterable, Optional

from three_col_circle_code.bench.plan_io import (
    load_instance_plan,
    load_plan_manifest,
    load_trial_plan,
    trial_result_path,
)
from three_col_circle_code.bench.records import (
    build_invalid_result_record,
    serialize_validation_errors,
)
from three_col_circle_code.instances.io import load_instance
from three_col_circle_code.instances.model import InstanceFormatError
from three_col_circle_code.instances.validate import validate_instance
from three_col_circle_code.solvers.common import SolverConfig
from three_col_circle_code.solvers.registry import run_solver


def run_trial(
    *,
    plan_dir: Path,
    index: int,
    work_root: Optional[Path] = None,
    force: bool = False,
) -> Path:
    """Run one planned solver trial and write its isolated result file."""
    trial_row = _select_trial_row(plan_dir=plan_dir, index=index)
    resolved_work_root = _resolve_work_root(plan_dir=plan_dir, work_root=work_root)
    result_path = trial_result_path(resolved_work_root, index)
    if result_path.exists() and not force:
        return result_path

    started_at = _now()
    try:
        record = load_instance(trial_row.instance_path)
    except (InstanceFormatError, json.JSONDecodeError, OSError) as exc:
        result = _build_invalid_result_record(
            trial=trial_row,
            started_at=started_at,
            error=exc,
        )
        _write_result(result_path, result)
        return result_path

    validation = validate_instance(record.graph, metadata=record.metadata.to_dict())
    validation_errors = serialize_validation_errors(validation.errors)
    solver_config = SolverConfig(
        solver=trial_row.solver,
        backend=trial_row.backend,
        params=dict(trial_row.solver_params),
        label=trial_row.solver_label,
    )
    warmup_measurements = _run_measurements(
        record=record,
        solver_config=solver_config,
        repetitions=trial_row.warmup_repetitions,
    )
    measurements = _run_measurements(
        record=record,
        solver_config=solver_config,
        repetitions=trial_row.repetitions,
    )
    result = _build_repeated_result_record(
        run_id=_run_id_for_plan(plan_dir),
        trial=trial_row,
        record=record,
        validation_ok=validation.ok,
        validation_errors=validation_errors,
        warmup_measurements=warmup_measurements,
        measurements=measurements,
        started_at=started_at,
    )
    _write_result(result_path, result)
    return result_path


def main(argv: Optional[Iterable[str]] = None) -> int:
    """Run one benchmark trial plan row from the command line."""
    parser = argparse.ArgumentParser(description="Run one benchmark trial plan row.")
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--index", type=int, required=True)
    parser.add_argument("--work-root", type=Path, default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        result_path = run_trial(
            plan_dir=args.plan_dir,
            index=args.index,
            work_root=args.work_root,
            force=args.force,
        )
    except ValueError as exc:
        print(f"benchmark trial failed: {exc}", file=sys.stderr)
        return 2
    print(result_path)
    return 0


def _select_trial_row(*, plan_dir: Path, index: int) -> Any:
    """Return the trial plan row with the requested 1-based index."""
    instances = load_instance_plan(plan_dir)
    rows = load_trial_plan(plan_dir, instances=instances)
    for row in rows:
        if row.index == index:
            return row
    raise ValueError(f"trial plan does not contain index {index}")


def _resolve_work_root(*, plan_dir: Path, work_root: Optional[Path]) -> Path:
    """Resolve the benchmark work root from an override or the plan manifest."""
    if work_root is not None:
        return Path(work_root)
    manifest = load_plan_manifest(plan_dir)
    try:
        return Path(str(manifest["work_root"]))
    except KeyError as exc:
        raise ValueError("plan manifest is missing required field 'work_root'") from exc


def _run_id_for_plan(plan_dir: Path) -> str:
    """Return the run id stored in the plan manifest, falling back to the directory name."""
    manifest = load_plan_manifest(plan_dir)
    return str(manifest.get("run_id", Path(plan_dir).name))


def _build_invalid_result_record(*, trial: Any, started_at: str, error: Exception) -> dict[str, Any]:
    """Build an invalid trial result row for a missing or malformed instance."""
    return build_invalid_result_record(
        run_id=None,
        index=trial.index,
        instance_id=trial.instance_id,
        instance_path=trial.instance_path,
        family=trial.family,
        n=trial.n,
        seed=trial.seed,
        solver_target=trial.solver_target,
        solver=trial.solver,
        backend=trial.backend,
        solver_params=dict(trial.solver_params),
        solver_label=trial.solver_label,
        error=error,
        extra_fields={
            "started_at": started_at,
            "finished_at": _now(),
            "repetitions": trial.repetitions,
            "warmup_repetitions": trial.warmup_repetitions,
            "ok_repetitions": 0,
            "mean_wall_time_s": None,
            "median_wall_time_s": None,
            "warmup_measurements": [],
            "measurements": [],
        },
    )


def _run_measurements(
    *,
    record: Any,
    solver_config: SolverConfig,
    repetitions: int,
) -> list[dict[str, Any]]:
    """Run the solver repeatedly and return compact measurement rows."""
    measurements: list[dict[str, Any]] = []
    for repetition in range(1, repetitions + 1):
        solve_result = run_solver(record, solver_config)
        measurements.append(
            {
                "repetition": repetition,
                "status": solve_result.status,
                "wall_time_s": solve_result.wall_time_s,
                "is_colorable": solve_result.is_colorable,
                "error": solve_result.error,
                "details": solve_result.details,
            }
        )
    return measurements


def _build_repeated_result_record(
    *,
    run_id: str,
    trial: Any,
    record: Any,
    validation_ok: bool,
    validation_errors: list[dict[str, Any]],
    warmup_measurements: list[dict[str, Any]],
    measurements: list[dict[str, Any]],
    started_at: str,
) -> dict[str, Any]:
    """Build the isolated trial result row for repeated measurements."""
    ok_measurements = [item for item in measurements if item["status"] == "ok"]
    wall_times = [
        float(item["wall_time_s"])
        for item in ok_measurements
        if item.get("wall_time_s") is not None
    ]
    answer_values = {
        item.get("is_colorable")
        for item in ok_measurements
        if item.get("is_colorable") is not None
    }
    last_measurement = measurements[-1] if measurements else {}
    status = "ok" if len(ok_measurements) == len(measurements) else "error"
    error = None
    if status != "ok":
        errors = [str(item.get("error")) for item in measurements if item.get("error")]
        error = "; ".join(errors) if errors else "one or more repetitions failed"
    return {
        "run_id": run_id,
        "index": trial.index,
        "instance_id": record.metadata.instance_id,
        "instance_path": str(trial.instance_path),
        "family": record.metadata.family,
        "bucket": record.metadata.bucket,
        "n": record.metadata.n,
        "m": record.metadata.m,
        "seed": record.metadata.seed,
        "source": record.metadata.source,
        "solver_target": trial.solver_target,
        "solver": trial.solver,
        "backend": trial.backend,
        "solver_params": dict(trial.solver_params),
        "solver_label": trial.solver_label,
        "status": status,
        "repetitions": trial.repetitions,
        "warmup_repetitions": trial.warmup_repetitions,
        "ok_repetitions": len(ok_measurements),
        "mean_wall_time_s": None if not wall_times else mean(wall_times),
        "median_wall_time_s": None if not wall_times else median(wall_times),
        "is_colorable": next(iter(answer_values)) if len(answer_values) == 1 else None,
        "validation_ok": validation_ok,
        "validation_errors": validation_errors,
        "details": dict(last_measurement.get("details", {})),
        "error": error,
        "warmup_measurements": warmup_measurements,
        "measurements": measurements,
        "started_at": started_at,
        "finished_at": _now(),
    }


def _write_result(path: Path, result: dict[str, Any]) -> None:
    """Write one isolated trial result JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as outfile:
        json.dump(result, outfile, indent=2, sort_keys=True)
        outfile.write("\n")


def _now() -> str:
    """Return the current UTC timestamp in ISO format."""
    return datetime.now(UTC).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
