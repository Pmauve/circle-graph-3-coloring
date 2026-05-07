import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
import sys
from typing import Any, Iterable, Optional

from three_col_circle_code.bench.env import collect_environment_metadata
from three_col_circle_code.bench.plan_io import (
    instance_result_path,
    load_instance_plan,
    load_plan_manifest,
)
from three_col_circle_code.generation.random_instances import generate_instance, write_instance_to_path
from three_col_circle_code.instances.io import load_instance
from three_col_circle_code.instances.model import InstanceFormatError, InstanceRecord
from three_col_circle_code.instances.native import (
    NativeInstanceError,
    NativeInstanceInvalid,
    ensure_validated_sidecar,
    generate_col_with_native,
    generate_col_sequence_with_native,
)
from three_col_circle_code.instances.validate import validate_instance


def run_instance_generation(
    *,
    plan_dir: Path,
    index: int,
    work_root: Optional[Path] = None,
    force: bool = False,
) -> Path:
    """Run one planned instance generation row and write its result file."""
    instance_row = _select_instance_row(plan_dir=plan_dir, index=index)
    resolved_work_root = _resolve_work_root(plan_dir=plan_dir, work_root=work_root)
    result_path = instance_result_path(resolved_work_root, index)
    if result_path.exists() and not force:
        existing = json.loads(result_path.read_text(encoding="utf-8"))
        if existing.get("status") in {"ok", "skipped"} and _existing_result_matches_plan(
            existing,
            instance_row=instance_row,
        ):
            return result_path

    started_at = _now()
    generated = False
    try:
        existing_info = _load_valid_existing_col_instance(instance_row.instance_path)
        if existing_info is None:
            existing_info = _load_valid_existing_instance(instance_row.instance_path)
        if existing_info is None:
            if Path(instance_row.instance_path).suffix == ".col":
                generate_col_with_native(
                    instance_path=instance_row.instance_path,
                    family=instance_row.family,
                    n=instance_row.n,
                    seed=instance_row.seed,
                    num_colors=instance_row.num_colors,
                )
                ensure_validated_sidecar(Path(instance_row.instance_path), force=True)
                validation_errors = []
                validation_ok = True
            else:
                record = generate_instance(
                    family=instance_row.family,
                    n=instance_row.n,
                    seed=instance_row.seed,
                    num_colors=instance_row.num_colors,
                )
                write_instance_to_path(record, instance_row.instance_path, atomic=True)
                loaded_record = load_instance(instance_row.instance_path)
                validation_ok, validation_errors = _validate_record(loaded_record)
            generated = True
        else:
            validation_errors = existing_info
            validation_ok = True
        status = "ok" if generated else "skipped"
        if not validation_ok:
            status = "invalid"
        result = _build_result(
            index=index,
            status=status,
            instance_id=instance_row.instance_id,
            instance_path=instance_row.instance_path,
            generated=generated,
            validation_ok=validation_ok,
            validation_errors=validation_errors,
            started_at=started_at,
            error=None,
            environment=collect_environment_metadata(),
        )
    except NativeInstanceInvalid as exc:
        result = _build_result(
            index=index,
            status="invalid",
            instance_id=instance_row.instance_id,
            instance_path=instance_row.instance_path,
            generated=generated,
            validation_ok=False,
            validation_errors=[{"code": "native_validation_failed", "message": str(exc)}],
            started_at=started_at,
            error=str(exc),
            environment=collect_environment_metadata(),
        )
    except Exception as exc:
        result = _build_result(
            index=index,
            status="error",
            instance_id=instance_row.instance_id,
            instance_path=instance_row.instance_path,
            generated=generated,
            validation_ok=False,
            validation_errors=[],
            started_at=started_at,
            error=str(exc),
            environment=collect_environment_metadata(),
        )
    _write_result(result_path, result)
    return result_path


def run_instance_sequence_generation(
    *,
    plan_dir: Path,
    index: int,
    work_root: Optional[Path] = None,
    force: bool = False,
) -> list[Path]:
    """Generate one grouped native instance sequence and write per-instance result files."""
    rows = load_instance_plan(plan_dir)
    groups = _native_sequence_groups(rows)
    if index < 1 or index > len(groups):
        raise ValueError(f"instance sequence plan does not contain index {index}")
    group = groups[index - 1]
    resolved_work_root = _resolve_work_root(plan_dir=plan_dir, work_root=work_root)
    if (
        not force
        and all(instance_result_path(resolved_work_root, row.index).exists() for row in group)
        and all(_existing_result_matches_plan(
            json.loads(instance_result_path(resolved_work_root, row.index).read_text(encoding="utf-8")),
            instance_row=row,
        ) for row in group)
    ):
        return [instance_result_path(resolved_work_root, row.index) for row in group]

    started_at = _now()
    result_paths: list[Path] = []
    try:
        first = group[0]
        start_n, stop_n, step_n = _sequence_bounds(group)
        generate_col_sequence_with_native(
            output_dir=_instance_pool_root_from_path(first.instance_path, first.family),
            family=first.family,
            start_n=start_n,
            stop_n=stop_n,
            step_n=step_n,
            seed=first.seed,
            num_colors=first.num_colors,
        )
        for row in group:
            ensure_validated_sidecar(row.instance_path, force=True)
            result = _build_result(
                index=row.index,
                status="ok",
                instance_id=row.instance_id,
                instance_path=row.instance_path,
                generated=True,
                validation_ok=True,
                validation_errors=[],
                started_at=started_at,
                error=None,
                environment=collect_environment_metadata(),
            )
            result_path = instance_result_path(resolved_work_root, row.index)
            _write_result(result_path, result)
            result_paths.append(result_path)
    except Exception as exc:
        for row in group:
            result = _build_result(
                index=row.index,
                status="error",
                instance_id=row.instance_id,
                instance_path=row.instance_path,
                generated=False,
                validation_ok=False,
                validation_errors=[],
                started_at=started_at,
                error=str(exc),
                environment=collect_environment_metadata(),
            )
            result_path = instance_result_path(resolved_work_root, row.index)
            _write_result(result_path, result)
            result_paths.append(result_path)
    return result_paths


def planned_instance_sequence_count(plan_dir: Path) -> int:
    """Return how many spec-declared native instance sequences are in a plan."""
    return len(_native_sequence_groups(load_instance_plan(plan_dir)))


def planned_instance_sequence_indices(plan_dir: Path) -> set[int]:
    """Return instance row indices covered by spec-declared native sequences."""
    return {
        row.index
        for group in _native_sequence_groups(load_instance_plan(plan_dir))
        for row in group
    }


def main(argv: Optional[Iterable[str]] = None) -> int:
    """Run one benchmark instance generation plan row from the command line."""
    parser = argparse.ArgumentParser(description="Run one benchmark instance generation plan row.")
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--index", type=int, required=True)
    parser.add_argument("--work-root", type=Path, default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        result_path = run_instance_generation(
            plan_dir=args.plan_dir,
            index=args.index,
            work_root=args.work_root,
            force=args.force,
        )
    except ValueError as exc:
        print(f"benchmark instance generation failed: {exc}", file=sys.stderr)
        return 2
    print(result_path)
    return 0


def sequence_main(argv: Optional[Iterable[str]] = None) -> int:
    """Run one grouped benchmark instance generation sequence from the command line."""
    parser = argparse.ArgumentParser(description="Run one benchmark instance generation sequence.")
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--index", type=int, required=True)
    parser.add_argument("--work-root", type=Path, default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        result_paths = run_instance_sequence_generation(
            plan_dir=args.plan_dir,
            index=args.index,
            work_root=args.work_root,
            force=args.force,
        )
    except ValueError as exc:
        print(f"benchmark instance sequence generation failed: {exc}", file=sys.stderr)
        return 2
    for path in result_paths:
        print(path)
    return 0


def _select_instance_row(*, plan_dir: Path, index: int) -> Any:
    """Return the instance plan row with the requested 1-based index."""
    rows = load_instance_plan(plan_dir)
    for row in rows:
        if row.index == index:
            return row
    raise ValueError(f"instance plan does not contain index {index}")


def _resolve_work_root(*, plan_dir: Path, work_root: Optional[Path]) -> Path:
    """Resolve the benchmark work root from an override or the plan manifest."""
    if work_root is not None:
        return Path(work_root)
    manifest = load_plan_manifest(plan_dir)
    try:
        return Path(str(manifest["work_root"]))
    except KeyError as exc:
        raise ValueError("plan manifest is missing required field 'work_root'") from exc


def _load_valid_existing_col_instance(instance_path: Path) -> Optional[list[dict[str, str]]]:
    """Validate or trust an existing DIMACS-circle file without materializing a Python graph."""
    if not Path(instance_path).exists() or Path(instance_path).suffix != ".col":
        return None
    ensure_validated_sidecar(Path(instance_path))
    return []


def _load_valid_existing_instance(instance_path: Path) -> Optional[list[dict[str, str]]]:
    """Load and validate an existing instance once."""
    if not Path(instance_path).exists():
        return None
    if Path(instance_path).suffix == ".col":
        return None
    try:
        record = load_instance(instance_path)
    except (InstanceFormatError, json.JSONDecodeError, OSError):
        return None
    validation_ok, _validation_errors = _validate_record(record)
    if not validation_ok:
        return None
    return _validation_errors


def _validate_record(record: InstanceRecord) -> tuple[bool, list[dict[str, str]]]:
    """Validate an instance record and serialize validation errors."""
    validation = validate_instance(record.graph, metadata=record.metadata.to_dict())
    return (
        validation.ok,
        [{"code": issue.code, "message": issue.message} for issue in validation.errors],
    )


def _build_result(
    *,
    index: int,
    status: str,
    instance_id: str,
    instance_path: Path,
    generated: bool,
    validation_ok: bool,
    validation_errors: list[dict[str, str]],
    started_at: str,
    error: Optional[str],
    environment: dict[str, Any],
) -> dict[str, Any]:
    """Build the isolated result record for one instance generation row."""
    return {
        "index": index,
        "kind": "instance",
        "status": status,
        "instance_id": instance_id,
        "instance_path": str(instance_path),
        "generated": generated,
        "validation_ok": validation_ok,
        "validation_errors": validation_errors,
        "started_at": started_at,
        "finished_at": _now(),
        "environment": environment,
        "error": error,
    }


def _existing_result_matches_plan(result: dict[str, Any], *, instance_row: Any) -> bool:
    """Return whether an isolated instance result still belongs to the current plan row."""
    return (
        result.get("index") == instance_row.index
        and result.get("instance_id") == instance_row.instance_id
        and str(result.get("instance_path")) == str(instance_row.instance_path)
    )


def _write_result(path: Path, result: dict[str, Any]) -> None:
    """Write one isolated instance generation result JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as outfile:
        json.dump(result, outfile, indent=2, sort_keys=True)
        outfile.write("\n")


def _now() -> str:
    """Return the current UTC timestamp in ISO format."""
    return datetime.now(UTC).isoformat()


def _native_sequence_groups(rows: tuple[Any, ...]) -> list[tuple[Any, ...]]:
    """Group native .col instance rows by one growable trajectory."""
    candidates = [
        row
        for row in rows
        if Path(row.instance_path).suffix == ".col" and getattr(row, "sequence_id", None) is not None
    ]
    grouped: dict[str, list[Any]] = {}
    for row in candidates:
        grouped.setdefault(str(row.sequence_id), []).append(row)
    groups: list[tuple[Any, ...]] = []
    for group_rows in grouped.values():
        ordered = tuple(sorted(group_rows, key=lambda row: row.n))
        if len(ordered) < 2:
            groups.append(ordered)
            continue
        _sequence_bounds(ordered)
        groups.append(ordered)
    return sorted(groups, key=lambda group: min(row.index for row in group))


def _sequence_bounds(rows: tuple[Any, ...]) -> tuple[int, int, int]:
    n_values = [row.n for row in rows]
    if len(n_values) == 1:
        return n_values[0], n_values[0], 1
    step = n_values[1] - n_values[0]
    if step < 1:
        raise ValueError("sequence n values must be strictly increasing")
    expected = list(range(n_values[0], n_values[-1] + 1, step))
    if n_values != expected:
        raise ValueError(f"sequence n values must form an arithmetic range; got {n_values}")
    return n_values[0], n_values[-1], step


def _instance_pool_root_from_path(instance_path: Path, family: str) -> Path:
    parts = list(Path(instance_path).parts)
    try:
        family_index = len(parts) - 1 - parts[::-1].index(family)
    except ValueError as exc:
        raise ValueError(f"cannot infer instance pool root from {instance_path}") from exc
    if family_index == 0:
        raise ValueError(f"cannot infer instance pool root from {instance_path}")
    return Path(*parts[:family_index])


if __name__ == "__main__":
    raise SystemExit(main())
