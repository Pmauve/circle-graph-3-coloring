import argparse
from datetime import UTC, datetime
from pathlib import Path
import sys
from typing import Any, Iterable, Optional

from three_col_circle_code.bench.plan_io import (
    PLAN_SPEC_FILENAME,
    InstancePlanRow,
    TrialPlanRow,
    write_instance_plan,
    write_plan_manifest,
    write_trial_plan,
)
from three_col_circle_code.bench.planning import (
    expected_instance_path,
    load_spec_for_run,
    resolve_existing_instance_path,
    validate_run_environment,
)
from three_col_circle_code.bench.results import normalize_run_label
from three_col_circle_code.bench.specs import RunSpec

DEFAULT_PLAN_ROOT = Path("eval") / "benchmark_plans"
DEFAULT_WORK_ROOT = Path("eval") / "benchmark_work"


def create_benchmark_plan(
    *,
    spec_path: Path,
    plan_root: Path = DEFAULT_PLAN_ROOT,
    work_root: Path = DEFAULT_WORK_ROOT,
    run_id: Optional[str] = None,
    force: bool = False,
) -> Path:
    spec_source, run_spec = load_spec_for_run(spec_path)
    validate_run_environment(run_spec)
    resolved_run_id = normalize_run_label(run_id or Path(spec_path).stem)
    plan_dir = Path(plan_root) / resolved_run_id
    plan_dir.mkdir(parents=True, exist_ok=True)
    _write_or_validate_spec_copy(plan_dir / PLAN_SPEC_FILENAME, spec_source=spec_source, force=force)

    instance_rows = _build_instance_plan_rows(run_spec)
    trial_rows = _build_trial_plan_rows(run_spec, instance_rows)
    write_instance_plan(plan_dir, instance_rows)
    write_trial_plan(plan_dir, trial_rows, instances=instance_rows)
    write_plan_manifest(
        plan_dir,
        _build_plan_manifest(
            run_id=resolved_run_id,
            run_spec=run_spec,
            work_root=Path(work_root) / resolved_run_id,
            n_instances=len(instance_rows),
            n_trials=len(trial_rows),
        ),
    )
    return plan_dir


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize a benchmark spec into reusable plan files.")
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--plan-root", type=Path, default=DEFAULT_PLAN_ROOT)
    parser.add_argument("--work-root", type=Path, default=DEFAULT_WORK_ROOT)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        plan_dir = create_benchmark_plan(
            spec_path=args.spec,
            plan_root=args.plan_root,
            work_root=args.work_root,
            run_id=args.run_id,
            force=args.force,
        )
    except ValueError as exc:
        print(f"benchmark plan failed: {exc}", file=sys.stderr)
        return 2
    print(plan_dir)
    return 0


def _build_instance_plan_rows(run_spec: RunSpec) -> tuple[InstancePlanRow, ...]:
    rows: list[InstancePlanRow] = []
    for index, request in enumerate(run_spec.instance_requests, start=1):
        existing_path, _resolution = resolve_existing_instance_path(
            instance_pool_root=run_spec.instance_pool_root,
            request=request,
        )
        instance_path = existing_path or expected_instance_path(
            instance_pool_root=run_spec.instance_pool_root,
            request=request,
        )
        rows.append(
            InstancePlanRow(
                index=index,
                instance_id=request.instance_id,
                family=request.family,
                n=request.n,
                seed=request.seed,
                instance_path=instance_path,
            )
        )
    return tuple(rows)


def _build_trial_plan_rows(
    run_spec: RunSpec,
    instance_rows: tuple[InstancePlanRow, ...],
) -> tuple[TrialPlanRow, ...]:
    rows: list[TrialPlanRow] = []
    for instance in instance_rows:
        for solver_config in run_spec.solver_configs:
            rows.append(
                TrialPlanRow(
                    index=len(rows) + 1,
                    instance_id=instance.instance_id,
                    instance_path=instance.instance_path,
                    family=instance.family,
                    n=instance.n,
                    seed=instance.seed,
                    solver=solver_config.solver,
                    backend=solver_config.backend,
                    solver_target=solver_config.target,
                    solver_params=dict(solver_config.params),
                    solver_label=solver_config.label,
                )
            )
    return tuple(rows)


def _build_plan_manifest(
    *,
    run_id: str,
    run_spec: RunSpec,
    work_root: Path,
    n_instances: int,
    n_trials: int,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "work_root": str(work_root),
        "n_instances": n_instances,
        "n_trials": n_trials,
    }


def _write_or_validate_spec_copy(spec_copy_path: Path, *, spec_source: str, force: bool) -> None:
    if spec_copy_path.exists():
        existing_source = spec_copy_path.read_text(encoding="utf-8")
        if existing_source != spec_source and not force:
            raise ValueError("existing benchmark plan was created from a different spec; use --force to replace it")
    spec_copy_path.write_text(spec_source, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
