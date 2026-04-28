from pathlib import Path
from typing import Any, Iterable, Optional

from three_col_circle_code.instances.model import InstanceRecord

BENCH_STATUS_INVALID = "invalid"


def build_benchmark_result_record(
    *,
    run_id: Optional[str],
    instance_path: Path,
    record: InstanceRecord,
    solver_target: str,
    solver_params: dict[str, Any],
    solver_label: Optional[str],
    validation_ok: bool,
    validation_errors: list[dict[str, Any]],
    solve_result: Any,
    index: Optional[int] = None,
    extra_fields: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build the normalized result row for one completed benchmark trial."""
    row = {
        "run_id": run_id,
        "instance_id": record.metadata.instance_id,
        "instance_path": str(instance_path),
        "family": record.metadata.family,
        "bucket": record.metadata.bucket,
        "n": record.metadata.n,
        "m": record.metadata.m,
        "seed": record.metadata.seed,
        "source": record.metadata.source,
        "solver_target": solver_target,
        "solver": solve_result.solver,
        "backend": solve_result.backend,
        "solver_params": dict(solver_params),
        "solver_label": solver_label,
        "status": solve_result.status,
        "wall_time_s": solve_result.wall_time_s,
        "is_colorable": solve_result.is_colorable,
        "validation_ok": validation_ok,
        "validation_errors": validation_errors,
        "details": solve_result.details,
        "error": solve_result.error,
    }
    if index is not None:
        row["index"] = index
    if extra_fields:
        row.update(extra_fields)
    return row


def build_invalid_result_record(
    *,
    run_id: Optional[str],
    instance_id: str,
    instance_path: Path,
    family: str,
    n: int,
    seed: int,
    solver_target: str,
    solver: str,
    backend: Optional[str],
    solver_params: dict[str, Any],
    solver_label: Optional[str],
    error: Exception,
    index: Optional[int] = None,
    extra_fields: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build the normalized result row for a trial whose instance could not load."""
    row = {
        "run_id": run_id,
        "instance_id": instance_id,
        "instance_path": str(instance_path),
        "family": family,
        "bucket": None,
        "n": n,
        "m": None,
        "seed": seed,
        "source": None,
        "solver_target": solver_target,
        "solver": solver,
        "backend": backend,
        "solver_params": dict(solver_params),
        "solver_label": solver_label,
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
    if index is not None:
        row["index"] = index
    if extra_fields:
        row.update(extra_fields)
    return row


def serialize_validation_errors(errors: Iterable[Any]) -> list[dict[str, Any]]:
    """Serialize validation issues into JSON-compatible dictionaries."""
    return [{"code": issue.code, "message": issue.message} for issue in errors]
