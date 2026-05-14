import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, median
import sys
from typing import Any, Iterable, Mapping, Optional

from three_col_circle_code.bench.env import collect_environment_metadata
from three_col_circle_code.bench.plan_io import (
    instance_result_path,
    load_instance_plan,
    load_plan_manifest,
    load_trial_plan,
    trial_result_path,
)
from three_col_circle_code.bench.records import (
    build_invalid_result_record,
)
from three_col_circle_code.bench.staging import staged_runtime_instance
from three_col_circle_code.instances.io import load_instance
from three_col_circle_code.instances.model import InstanceFormatError, InstanceMetadata, bucket_for_n
from three_col_circle_code.instances.native import (
    NativeInstanceError,
    NativeInstanceInvalid,
    ensure_validated_sidecar,
)
from three_col_circle_code.solvers.common import SolverConfig
from three_col_circle_code.solvers.registry import run_solver_from_path as run_solver
from three_col_circle_code.solvers.sat_native import SAT_3_COL_NATIVE_SOLVER
from three_col_circle_code.solvers.sosa.native import SOSA_3_COL_NATIVE_SOLVER
from three_col_circle_code.solvers.zykovcolor import ZYKOVCOLOR_SOLVER


@dataclass(frozen=True)
class TrialContext:
    """Resolved plan data needed to run one trial."""

    trial: Any
    instances: tuple[Any, ...]
    work_root: Path
    run_id: str


def run_trial(
    *,
    plan_dir: Path,
    index: int,
    work_root: Optional[Path] = None,
    force: bool = False,
    validate_instance_artifact: bool = False,
    runtime_instance_path: Optional[Path] = None,
) -> Path:
    """Run one planned solver trial and write its isolated result file."""
    context = _load_trial_context(plan_dir=plan_dir, index=index, work_root=work_root)
    trial_row = context.trial
    result_path = trial_result_path(context.work_root, index)
    if result_path.exists() and not force:
        existing = json.loads(result_path.read_text(encoding="utf-8"))
        if _existing_result_matches_plan(existing, trial=trial_row):
            return result_path

    started_at = _now()
    try:
        validation_ok, validation_errors = _load_cached_instance_validation(
            instances=context.instances,
            work_root=context.work_root,
            trial=trial_row,
        )
    except ValueError as exc:
        result = _build_invalid_result_record(
            run_id=context.run_id,
            trial=trial_row,
            started_at=started_at,
            error=exc,
        )
        _write_result(result_path, result)
        return result_path
    if validate_instance_artifact and trial_row.instance_path.suffix in {".col", ".circle"}:
        try:
            ensure_validated_sidecar(trial_row.instance_path, force=True)
        except NativeInstanceInvalid as exc:
            result = _build_invalid_result_record(
                run_id=context.run_id,
                trial=trial_row,
                started_at=started_at,
                error=exc,
            )
            _write_result(result_path, result)
            return result_path
        except NativeInstanceError as exc:
            raise ValueError(str(exc)) from exc
    solver_config = SolverConfig(
        solver=trial_row.solver,
        backend=trial_row.backend,
        params=dict(trial_row.solver_params),
        label=trial_row.solver_label,
    )
    if (
        runtime_instance_path is None
        and trial_row.instance_path.suffix == ".circle"
        and not _uses_path_without_python_graph(solver_config)
    ):
        with staged_runtime_instance(trial_row.instance_path) as runtime_path:
            return run_trial(
                plan_dir=plan_dir,
                index=index,
                work_root=work_root,
                force=force,
                validate_instance_artifact=validate_instance_artifact,
                runtime_instance_path=runtime_path,
            )
    if _uses_path_without_python_graph(solver_config):
        try:
            instance_metadata = _load_path_solver_metadata(trial_row)
        except (InstanceFormatError, OSError) as exc:
            result = _build_invalid_result_record(
                run_id=context.run_id,
                trial=trial_row,
                started_at=started_at,
                error=exc,
            )
            _write_result(result_path, result)
            return result_path
    else:
        try:
            load_path = Path(runtime_instance_path) if runtime_instance_path is not None else trial_row.instance_path
            record = load_instance(load_path, validate=validate_instance_artifact)
        except (InstanceFormatError, json.JSONDecodeError, OSError, MemoryError) as exc:
            result = _build_invalid_result_record(
                run_id=context.run_id,
                trial=trial_row,
                started_at=started_at,
                error=exc,
            )
            _write_result(result_path, result)
            return result_path
        instance_metadata = record.metadata

    if runtime_instance_path is not None:
        runtime_path = Path(runtime_instance_path)
        warmup_measurements, _warmup_details = _run_measurements(
            solver_config=solver_config,
            instance_path=runtime_path,
            validate_instance_artifact=validate_instance_artifact,
            repetitions=trial_row.warmup_repetitions,
        )
        measurements, measurement_details = _run_measurements(
            solver_config=solver_config,
            instance_path=runtime_path,
            validate_instance_artifact=validate_instance_artifact,
            repetitions=trial_row.repetitions,
        )
    else:
        with staged_runtime_instance(trial_row.instance_path) as runtime_path:
            warmup_measurements, _warmup_details = _run_measurements(
                solver_config=solver_config,
                instance_path=runtime_path,
                validate_instance_artifact=validate_instance_artifact,
                repetitions=trial_row.warmup_repetitions,
            )
            measurements, measurement_details = _run_measurements(
                solver_config=solver_config,
                instance_path=runtime_path,
                validate_instance_artifact=validate_instance_artifact,
                repetitions=trial_row.repetitions,
            )
    result = _build_repeated_result_record(
        run_id=context.run_id,
        trial=trial_row,
        instance_metadata=instance_metadata,
        validation_ok=validation_ok,
        validation_errors=validation_errors,
        warmup_measurements=warmup_measurements,
        measurements=measurements,
        measurement_details=measurement_details,
        started_at=started_at,
        environment=collect_environment_metadata(),
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
    parser.add_argument("--validate-instance", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        result_path = run_trial(
            plan_dir=args.plan_dir,
            index=args.index,
            work_root=args.work_root,
            force=args.force,
            validate_instance_artifact=args.validate_instance,
        )
    except ValueError as exc:
        print(f"benchmark trial failed: {exc}", file=sys.stderr)
        return 2
    print(result_path)
    return 0


def _load_trial_context(*, plan_dir: Path, index: int, work_root: Optional[Path]) -> TrialContext:
    """Load the plan files once and select the requested trial."""
    instances = load_instance_plan(plan_dir)
    rows = load_trial_plan(plan_dir, instances=instances)
    manifest = load_plan_manifest(plan_dir)
    for row in rows:
        if row.index == index:
            return TrialContext(
                trial=row,
                instances=instances,
                work_root=Path(work_root) if work_root is not None else Path(str(manifest["work_root"])),
                run_id=str(manifest.get("run_id", Path(plan_dir).name)),
            )
    raise ValueError(f"trial plan does not contain index {index}")


def _load_cached_instance_validation(
    *,
    instances: tuple[Any, ...],
    work_root: Path,
    trial: Any,
) -> tuple[bool, list[dict[str, Any]]]:
    """Load validation data written by the matching instance generation task."""
    instance_row = next((row for row in instances if row.instance_id == trial.instance_id), None)
    if instance_row is None:
        raise ValueError(f"trial {trial.index} references unknown instance id {trial.instance_id!r}")

    result_path = instance_result_path(work_root, instance_row.index)
    if not result_path.exists():
        raise ValueError(
            f"missing instance generation result for {trial.instance_id!r}; "
            f"run benchmark_generate_instance --index {instance_row.index} first"
        )
    result = json.loads(result_path.read_text(encoding="utf-8"))
    status = str(result.get("status"))
    if result.get("instance_id") != trial.instance_id:
        raise ValueError(
            f"instance generation result {instance_row.index} belongs to "
            f"{result.get('instance_id')!r}, expected {trial.instance_id!r}"
        )
    if str(result.get("instance_path")) != str(trial.instance_path):
        raise ValueError(f"instance generation result {instance_row.index} path does not match trial plan")
    if status not in {"ok", "skipped"}:
        error = result.get("error")
        suffix = f": {error}" if error else ""
        raise ValueError(f"instance generation result for {trial.instance_id!r} is {status}{suffix}")
    validation_ok = bool(result.get("validation_ok", False))
    validation_errors = result.get("validation_errors", [])
    if not isinstance(validation_errors, list):
        raise ValueError(f"instance generation result for {trial.instance_id!r} has invalid validation_errors")
    if not validation_ok:
        raise ValueError(f"instance generation result for {trial.instance_id!r} did not validate successfully")
    return validation_ok, [dict(item) for item in validation_errors]


def _build_invalid_result_record(
    *,
    trial: Any,
    started_at: str,
    error: Exception,
    run_id: Optional[str] = None,
) -> dict[str, Any]:
    """Build an invalid trial result row for a missing or malformed instance."""
    return build_invalid_result_record(
        run_id=run_id,
        index=trial.index,
        instance_id=trial.instance_id,
        instance_path=trial.instance_path,
        family=trial.family,
        n=trial.n,
        seed=trial.seed,
        num_colors=trial.num_colors,
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
            "family_label": trial.family_label,
            "generator_params": dict(trial.generator_params),
            "output_format": trial.output_format,
            "ok_repetitions": 0,
            "mean_wall_time_s": None,
            "median_wall_time_s": None,
            "mean_total_native_time_s": None,
            "median_total_native_time_s": None,
            "mean_load_prepare_time_s": None,
            "median_load_prepare_time_s": None,
            "mean_solve_time_s": None,
            "median_solve_time_s": None,
            "mean_peak_rss_kb": None,
            "median_peak_rss_kb": None,
            "max_peak_rss_kb": None,
            "average_degree": None,
            "warmup_measurements": [],
            "measurements": [],
            "environment": collect_environment_metadata(),
        },
    )


def _run_measurements(
    *,
    solver_config: SolverConfig,
    instance_path: Path,
    validate_instance_artifact: bool,
    repetitions: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the solver repeatedly and return compact measurement rows."""
    measurements: list[dict[str, Any]] = []
    last_details: dict[str, Any] = {}
    for repetition in range(1, repetitions + 1):
        try:
            solve_result = run_solver(
                instance_path,
                solver_config,
                validate_instance_artifact=validate_instance_artifact,
            )
        except Exception as exc:
            last_details = {
                "error_type": type(exc).__name__,
                "solver_target": solver_config.target,
            }
            measurements.append(
                {
                    "repetition": repetition,
                    "status": "error",
                    "wall_time_s": None,
                    "total_native_time_s": None,
                    "load_prepare_time_s": None,
                    "solve_time_s": None,
                    "peak_rss_kb": None,
                    "is_colorable": None,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        last_details = dict(solve_result.details)
        load_prepare_time_s = _optional_float_from_mapping(last_details, "load_prepare_time_s")
        solve_time_s = _optional_float_from_mapping(last_details, "solve_time_s")
        total_native_time_s = solve_result.total_native_time_s
        if total_native_time_s is None:
            total_native_time_s = _optional_float_from_mapping(last_details, "total_native_time_s")
        measurements.append(
            {
                "repetition": repetition,
                "status": solve_result.status,
                "wall_time_s": solve_result.wall_time_s,
                "total_native_time_s": total_native_time_s,
                "load_prepare_time_s": load_prepare_time_s,
                "solve_time_s": solve_time_s,
                "peak_rss_kb": solve_result.peak_rss_kb,
                "is_colorable": solve_result.is_colorable,
                "error": solve_result.error,
            }
        )
    return measurements, last_details


def _build_repeated_result_record(
    *,
    run_id: str,
    trial: Any,
    instance_metadata: InstanceMetadata,
    validation_ok: bool,
    validation_errors: list[dict[str, Any]],
    warmup_measurements: list[dict[str, Any]],
    measurements: list[dict[str, Any]],
    measurement_details: dict[str, Any],
    started_at: str,
    environment: dict[str, Any],
) -> dict[str, Any]:
    """Build the isolated trial result row for repeated measurements."""
    ok_measurements = [item for item in measurements if item["status"] == "ok"]
    wall_times = [
        float(item["wall_time_s"])
        for item in ok_measurements
        if item.get("wall_time_s") is not None
    ]
    total_native_times = [
        float(item["total_native_time_s"])
        for item in ok_measurements
        if item.get("total_native_time_s") is not None
    ]
    load_prepare_times = [
        float(item["load_prepare_time_s"])
        for item in ok_measurements
        if item.get("load_prepare_time_s") is not None
    ]
    solve_times = [
        float(item["solve_time_s"])
        for item in ok_measurements
        if item.get("solve_time_s") is not None
    ]
    peak_rss_values = [
        int(item["peak_rss_kb"])
        for item in ok_measurements
        if item.get("peak_rss_kb") is not None
    ]
    answer_values = {
        item.get("is_colorable")
        for item in ok_measurements
        if item.get("is_colorable") is not None
    }
    has_inconsistent_answers = len(answer_values) > 1
    status = "ok" if len(ok_measurements) == len(measurements) and not has_inconsistent_answers else "error"
    error = None
    if has_inconsistent_answers:
        error = "repetitions returned inconsistent is_colorable values"
    elif status != "ok":
        errors = [str(item.get("error")) for item in measurements if item.get("error")]
        error = "; ".join(errors) if errors else "one or more repetitions failed"
    return {
        "run_id": run_id,
        "index": trial.index,
        "instance_id": trial.instance_id,
        "instance_path": str(trial.instance_path),
        "family": instance_metadata.family,
        "family_label": trial.family_label,
        "generator_params": dict(trial.generator_params),
        "output_format": trial.output_format,
        "bucket": instance_metadata.bucket,
        "n": instance_metadata.n,
        "m": instance_metadata.m,
        "average_degree": _average_degree(instance_metadata.n, instance_metadata.m),
        "seed": instance_metadata.seed,
        "num_colors": instance_metadata.num_colors,
        "source": instance_metadata.source,
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
        "mean_total_native_time_s": None if not total_native_times else mean(total_native_times),
        "median_total_native_time_s": None if not total_native_times else median(total_native_times),
        "mean_load_prepare_time_s": None if not load_prepare_times else mean(load_prepare_times),
        "median_load_prepare_time_s": None if not load_prepare_times else median(load_prepare_times),
        "mean_solve_time_s": None if not solve_times else mean(solve_times),
        "median_solve_time_s": None if not solve_times else median(solve_times),
        "mean_peak_rss_kb": None if not peak_rss_values else mean(peak_rss_values),
        "median_peak_rss_kb": None if not peak_rss_values else median(peak_rss_values),
        "max_peak_rss_kb": None if not peak_rss_values else max(peak_rss_values),
        "is_colorable": next(iter(answer_values)) if len(answer_values) == 1 else None,
        "validation_ok": validation_ok,
        "validation_errors": validation_errors,
        "details": dict(measurement_details),
        "error": error,
        "warmup_measurements": warmup_measurements,
        "measurements": measurements,
        "started_at": started_at,
        "finished_at": _now(),
        "environment": environment,
    }


def _existing_result_matches_plan(result: dict[str, Any], *, trial: Any) -> bool:
    """Return whether an isolated trial result still belongs to the current plan row."""
    return (
        result.get("index") == trial.index
        and result.get("instance_id") == trial.instance_id
        and str(result.get("instance_path")) == str(trial.instance_path)
        and result.get("num_colors") == trial.num_colors
        and result.get("solver_target") == trial.solver_target
        and result.get("solver") == trial.solver
        and result.get("backend") == trial.backend
        and result.get("solver_label") == trial.solver_label
        and result.get("family_label") == trial.family_label
        and dict(result.get("generator_params", {})) == dict(trial.generator_params)
        and result.get("output_format", "circle") == trial.output_format
        and dict(result.get("solver_params", {})) == dict(trial.solver_params)
        and result.get("repetitions") == trial.repetitions
        and result.get("warmup_repetitions") == trial.warmup_repetitions
    )


def _uses_path_without_python_graph(solver_config: SolverConfig) -> bool:
    return solver_config.solver in {SAT_3_COL_NATIVE_SOLVER, SOSA_3_COL_NATIVE_SOLVER, ZYKOVCOLOR_SOLVER}


def _optional_float_from_mapping(values: dict[str, Any], key: str) -> Optional[float]:
    value = values.get(key)
    if value is None:
        return None
    return float(value)


def _load_path_solver_metadata(trial: Any) -> InstanceMetadata:
    """Read cheap instance metadata for path-native solvers without materializing the graph."""
    if not trial.instance_path.exists():
        raise FileNotFoundError(trial.instance_path)
    comments, n_vertices, n_edges = _read_dimacs_header(trial.instance_path)
    return InstanceMetadata(
        instance_id=trial.instance_id,
        family=comments.get("family", trial.family),
        seed=trial.seed,
        generator=comments.get("generator", "benchmark_plan"),
        n=n_vertices,
        m=n_edges,
        num_colors=int(comments.get("num_colors", trial.num_colors)),
        bucket=bucket_for_n(n_vertices),
        source=comments.get("source", "existing"),
        created_at=comments.get("created_at", "unknown"),
    )


def _read_dimacs_header(path: Path) -> tuple[dict[str, str], int, int]:
    comments: dict[str, str] = {}
    metadata_keys = {
        ("family",): "family",
        ("generator",): "generator",
        ("source",): "source",
        ("created", "at"): "created_at",
        ("num", "colors"): "num_colors",
        ("m",): "m",
    }
    with path.open(encoding="utf-8") as infile:
        for raw_line in infile:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("c "):
                parts = line[2:].split()
                for key_parts, key in metadata_keys.items():
                    if tuple(parts[: len(key_parts)]) == key_parts and len(parts) > len(key_parts):
                        comments[key] = " ".join(parts[len(key_parts) :])
                continue
            fields = line.split()
            if len(fields) == 4 and fields[0] == "p" and fields[1] in {"edge", "col", "circle"}:
                return comments, int(fields[2]), int(fields[3])
            raise InstanceFormatError(f"unexpected DIMACS header line in {path}: {line!r}")
    raise InstanceFormatError(f"missing DIMACS problem line in {path}")


def _write_result(path: Path, result: dict[str, Any]) -> None:
    """Write one isolated trial result JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as outfile:
        json.dump(_json_ready(result), outfile, indent=2, sort_keys=True)
        outfile.write("\n")


def _json_ready(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    return str(value)


def _now() -> str:
    """Return the current UTC timestamp in ISO format."""
    return datetime.now(UTC).isoformat()


def _average_degree(n_vertices: int, n_edges: int) -> float:
    if n_vertices == 0:
        return 0.0
    return 2.0 * n_edges / n_vertices


if __name__ == "__main__":
    raise SystemExit(main())
