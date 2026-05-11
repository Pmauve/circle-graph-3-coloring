import argparse
import json
from pathlib import Path
import sys
from typing import Iterable, Optional

from three_col_circle_code.bench.generate_instance import run_instance_sequence_generation
from three_col_circle_code.bench.plan_io import instance_result_path
from three_col_circle_code.bench.run_trial import run_trial
from three_col_circle_code.bench.sequences import (
    select_native_sequence_group,
    trial_rows_by_instance_index,
)
from three_col_circle_code.bench.staging import staged_runtime_instance


def run_instance_sequence(
    *,
    plan_dir: Path,
    index: int,
    work_root: Optional[Path] = None,
    force: bool = False,
    validate_instance_artifact: bool = False,
    keep_instances: bool = False,
) -> list[Path]:
    """Generate one native instance sequence and run its trials against staged runtime files."""
    group = select_native_sequence_group(plan_dir, index)
    result_paths = run_instance_sequence_generation(
        plan_dir=plan_dir,
        index=index,
        work_root=work_root,
        force=force,
    )
    trial_rows = trial_rows_by_instance_index(plan_dir)
    for instance_row in group:
        instance_status = _instance_generation_status(
            work_root=Path(work_root) if work_root is not None else _default_work_root(plan_dir),
            index=instance_row.index,
        )
        if instance_status not in {"ok", "skipped"}:
            for trial_row in trial_rows.get(instance_row.index, ()):
                result_paths.append(
                    run_trial(
                        plan_dir=plan_dir,
                        index=trial_row.index,
                        work_root=work_root,
                        force=force,
                        validate_instance_artifact=validate_instance_artifact,
                    )
                )
            continue
        with staged_runtime_instance(instance_row.instance_path) as runtime_path:
            for trial_row in trial_rows.get(instance_row.index, ()):
                result_paths.append(
                    run_trial(
                        plan_dir=plan_dir,
                        index=trial_row.index,
                        work_root=work_root,
                        force=force,
                        validate_instance_artifact=validate_instance_artifact,
                        runtime_instance_path=runtime_path,
                    )
                )
    return result_paths


def _default_work_root(plan_dir: Path) -> Path:
    manifest = json.loads((Path(plan_dir) / "manifest.json").read_text(encoding="utf-8"))
    return Path(str(manifest["work_root"]))


def _instance_generation_status(*, work_root: Path, index: int) -> Optional[str]:
    result_path = instance_result_path(work_root, index)
    if not result_path.exists():
        return None
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return str(result.get("status"))


def main(argv: Optional[Iterable[str]] = None) -> int:
    """Run one benchmark native sequence and all trials that use it."""
    parser = argparse.ArgumentParser(description="Run one benchmark instance sequence and its trials.")
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--index", type=int, required=True)
    parser.add_argument("--work-root", type=Path, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--validate-instance", action="store_true")
    parser.add_argument("--keep-instances", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        result_paths = run_instance_sequence(
            plan_dir=args.plan_dir,
            index=args.index,
            work_root=args.work_root,
            force=args.force,
            validate_instance_artifact=args.validate_instance,
            keep_instances=args.keep_instances,
        )
    except ValueError as exc:
        print(f"benchmark instance sequence run failed: {exc}", file=sys.stderr)
        return 2
    for path in result_paths:
        print(path)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
