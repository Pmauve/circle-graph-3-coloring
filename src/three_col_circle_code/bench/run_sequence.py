import argparse
from pathlib import Path
import sys
from typing import Iterable, Optional

from three_col_circle_code.bench.generate_instance import run_instance_sequence_generation
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
