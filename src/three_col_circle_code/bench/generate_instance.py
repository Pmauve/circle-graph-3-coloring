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
        if existing.get("status") in {"ok", "skipped"}:
            return result_path

    started_at = _now()
    generated = False
    try:
        existing_info = _load_valid_existing_instance(instance_row.instance_path)
        if existing_info is None:
            record = generate_instance(
                family=instance_row.family,
                n=instance_row.n,
                seed=instance_row.seed,
                num_colors=instance_row.num_colors,
            )
            write_instance_to_path(record, instance_row.instance_path, atomic=True)
            generated = True
            loaded_record = load_instance(instance_row.instance_path)
            validation_ok, validation_errors = _validate_record(loaded_record)
        else:
            loaded_record, validation_errors = existing_info
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


def _load_valid_existing_instance(instance_path: Path) -> Optional[tuple[InstanceRecord, list[dict[str, str]]]]:
    """Load and validate an existing instance once."""
    if not Path(instance_path).exists():
        return None
    try:
        record = load_instance(instance_path)
    except (InstanceFormatError, json.JSONDecodeError, OSError):
        return None
    validation_ok, _validation_errors = _validate_record(record)
    if not validation_ok:
        return None
    return record, _validation_errors


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


def _write_result(path: Path, result: dict[str, Any]) -> None:
    """Write one isolated instance generation result JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as outfile:
        json.dump(result, outfile, indent=2, sort_keys=True)
        outfile.write("\n")


def _now() -> str:
    """Return the current UTC timestamp in ISO format."""
    return datetime.now(UTC).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
