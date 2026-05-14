import argparse
import json
from pathlib import Path
import sys
from typing import Any, Iterable, Optional

from three_col_circle_code.bench.env import collect_environment_metadata
from three_col_circle_code.bench.plan_io import (
    PLAN_SPEC_FILENAME,
    load_instance_plan,
    load_plan_manifest,
    load_trial_plan,
    trial_result_path,
)
from three_col_circle_code.bench.planning import (
    build_run_manifest,
    load_spec_for_run,
    prepare_run_directory,
)
from three_col_circle_code.bench.report import build_benchmark_report
from three_col_circle_code.bench.report_data import write_summary_csvs
from three_col_circle_code.bench.results import DEFAULT_RUNS_ROOT, RESULTS_FILENAME, write_manifest
from three_col_circle_code.bench.specs import canonical_params_json


def merge_benchmark_results(
    *,
    plan_dir: Path,
    work_root: Optional[Path] = None,
    output_root: Path = DEFAULT_RUNS_ROOT,
    run_id: Optional[str] = None,
    allow_missing: bool = False,
    force: bool = False,
) -> Path:
    """Merge isolated trial result files into a standard benchmark run directory."""
    plan_dir = Path(plan_dir)
    spec_path = plan_dir / PLAN_SPEC_FILENAME
    spec_source, run_spec = load_spec_for_run(spec_path)
    plan_manifest = load_plan_manifest(plan_dir)
    resolved_run_id = run_id or str(plan_manifest.get("run_id", plan_dir.name))
    resolved_work_root = Path(work_root) if work_root is not None else Path(str(plan_manifest["work_root"]))
    instances = load_instance_plan(plan_dir)
    trials = load_trial_plan(plan_dir, instances=instances)
    rows, missing_indices = _load_trial_results(
        trials=trials,
        work_root=resolved_work_root,
        allow_missing=allow_missing,
    )
    run_dir = prepare_run_directory(
        output_root=output_root,
        spec_source=spec_source,
        run_id=resolved_run_id,
    )
    results_path = run_dir / RESULTS_FILENAME
    if results_path.exists() and not force:
        raise ValueError(f"merged results already exist at {results_path}; use --force to rebuild them")

    _write_results_jsonl(results_path, rows)
    manifest = build_run_manifest(
        run_id=run_dir.name,
        run_spec=run_spec,
        created_at=None,
        environment=collect_environment_metadata(),
    )
    manifest.update(
        {
            "execution_mode": "merged_trial_outputs",
            "plan_dir": str(plan_dir),
            "work_root": str(resolved_work_root),
            "n_expected_trials": len(trials),
            "n_merged_trials": len(rows),
            "missing_trial_indices": missing_indices,
        }
    )
    write_manifest(run_dir, manifest)
    write_summary_csvs(run_dir)
    build_benchmark_report(run_dir)
    return run_dir


def main(argv: Optional[Iterable[str]] = None) -> int:
    """Merge benchmark trial outputs from the command line."""
    parser = argparse.ArgumentParser(description="Merge isolated benchmark trial outputs into one reportable run.")
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_RUNS_ROOT)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--allow-missing", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        run_dir = merge_benchmark_results(
            plan_dir=args.plan_dir,
            work_root=args.work_root,
            output_root=args.output_root,
            run_id=args.run_id,
            allow_missing=args.allow_missing,
            force=args.force,
        )
    except ValueError as exc:
        print(f"benchmark merge failed: {exc}", file=sys.stderr)
        return 2
    print(run_dir)
    return 0


def _load_trial_results(
    *,
    trials: Iterable[Any],
    work_root: Path,
    allow_missing: bool,
) -> tuple[list[dict[str, Any]], list[int]]:
    """Load and validate trial result files for the planned trials."""
    rows: list[dict[str, Any]] = []
    missing_indices: list[int] = []
    seen_indices: set[int] = set()
    for trial in trials:
        result_path = trial_result_path(work_root, trial.index)
        if not result_path.exists():
            missing_indices.append(trial.index)
            continue
        row = json.loads(result_path.read_text(encoding="utf-8"))
        _validate_trial_result(row=row, trial=trial)
        if trial.index in seen_indices:
            raise ValueError(f"duplicate trial result for index {trial.index}")
        seen_indices.add(trial.index)
        rows.append(row)
    if missing_indices and not allow_missing:
        raise ValueError("missing trial result(s): " + ", ".join(str(index) for index in missing_indices))
    return rows, missing_indices


def _validate_trial_result(*, row: dict[str, Any], trial: Any) -> None:
    """Validate that one trial result belongs to its planned trial row."""
    expected_params = canonical_params_json(trial.solver_params)
    actual_params = canonical_params_json(row.get("solver_params", {}))
    checks = {
        "index": trial.index,
        "instance_id": trial.instance_id,
        "instance_path": str(trial.instance_path),
        "num_colors": trial.num_colors,
        "solver_target": trial.solver_target,
        "solver": trial.solver,
        "backend": trial.backend,
        "solver_label": trial.solver_label,
        "repetitions": trial.repetitions,
        "warmup_repetitions": trial.warmup_repetitions,
    }
    for field, expected in checks.items():
        if row.get(field) != expected:
            raise ValueError(
                f"trial result {trial.index} field {field!r} does not match plan "
                f"(expected {expected!r}, got {row.get(field)!r})"
            )
    if actual_params != expected_params:
        raise ValueError(f"trial result {trial.index} solver_params do not match plan")


def _write_results_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    """Write merged trial rows to the standard benchmark results JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as outfile:
        for row in sorted(rows, key=lambda item: int(item["index"])):
            outfile.write(json.dumps(row, sort_keys=True))
            outfile.write("\n")


if __name__ == "__main__":
    raise SystemExit(main())
