import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
from pathlib import Path
import shutil
import sys
from typing import Callable, Iterable, Optional, TextIO

from three_col_circle_code.bench.generate_instance import (
    planned_instance_sequence_count,
    planned_instance_sequence_indices,
    run_instance_generation,
    run_instance_sequence_generation,
)
from three_col_circle_code.bench.merge import merge_benchmark_results
from three_col_circle_code.bench.plan import DEFAULT_PLAN_ROOT, DEFAULT_WORK_ROOT, create_benchmark_plan
from three_col_circle_code.bench.plan_io import (
    InstancePlanRow,
    TrialPlanRow,
    instance_result_path,
    load_instance_plan,
    load_plan_manifest,
    load_trial_plan,
)
from three_col_circle_code.bench.results import DEFAULT_RUNS_ROOT, RESULTS_FILENAME
from three_col_circle_code.bench.run_trial import run_trial


def run_benchmark(
    *,
    output_root: Path,
    spec_path: Path,
    progress_stream: TextIO | None = None,
    jobs: int = 1,
    run_id: Optional[str] = None,
    plan_root: Path = DEFAULT_PLAN_ROOT,
    work_root: Path = DEFAULT_WORK_ROOT,
    force: bool = False,
    allow_missing: bool = False,
) -> Path:
    """Run a local benchmark pipeline from spec to merged report."""
    if jobs < 1:
        raise ValueError("--jobs must be at least 1")

    _emit_progress(progress_stream, f"Planning benchmark from {Path(spec_path)}")
    plan_dir = create_benchmark_plan(
        spec_path=spec_path,
        plan_root=plan_root,
        work_root=work_root,
        run_id=run_id,
        force=force,
    )
    manifest = load_plan_manifest(plan_dir)
    resolved_work_root = Path(str(manifest["work_root"]))
    instance_rows = load_instance_plan(plan_dir)
    trial_rows = load_trial_plan(plan_dir, instances=instance_rows)

    _emit_progress(progress_stream, f"Plan directory: {plan_dir}")
    _emit_progress(progress_stream, f"Work directory: {resolved_work_root}")
    _emit_progress(progress_stream, f"Preparing {len(instance_rows)} instance(s) with jobs={jobs}")
    sequence_count = planned_instance_sequence_count(plan_dir)
    sequenced_indices = planned_instance_sequence_indices(plan_dir)
    if sequence_count:
        _run_index_phase(
            phase="instance sequence preparation",
            indices=tuple(range(1, sequence_count + 1)),
            jobs=jobs,
            worker=_run_instance_sequence_generation_job,
            plan_dir=plan_dir,
            force=force,
            progress_stream=progress_stream,
        )
    remaining_instance_rows = tuple(row for row in instance_rows if row.index not in sequenced_indices)
    _run_phase(
        phase="instance preparation",
        rows=remaining_instance_rows,
        jobs=jobs,
        worker=_run_instance_generation_job,
        plan_dir=plan_dir,
        force=force,
        progress_stream=progress_stream,
    )
    _ensure_instance_generation_succeeded(
        work_root=resolved_work_root,
        rows=instance_rows,
    )
    for line in _instance_preparation_details(work_root=resolved_work_root, rows=instance_rows):
        _emit_progress(progress_stream, line)
    _emit_progress(
        progress_stream,
        _instance_preparation_summary(work_root=resolved_work_root, rows=instance_rows),
    )

    _emit_progress(progress_stream, f"Running {len(trial_rows)} trial(s) with jobs={jobs}")
    _run_phase(
        phase="trial",
        rows=trial_rows,
        jobs=jobs,
        worker=_run_trial_job,
        plan_dir=plan_dir,
        force=force,
        progress_stream=progress_stream,
    )

    _emit_progress(progress_stream, "Merging trial outputs")
    run_dir = merge_benchmark_results(
        plan_dir=plan_dir,
        output_root=output_root,
        allow_missing=allow_missing,
        force=True,
    )
    _emit_progress(progress_stream, f"Results: {run_dir / RESULTS_FILENAME}")
    _emit_progress(progress_stream, f"Report: {run_dir / 'report.html'}")
    if not allow_missing:
        _cleanup_successful_work_dirs(
            plan_dir=plan_dir,
            work_root=resolved_work_root,
            progress_stream=progress_stream,
        )
    return run_dir


def main(argv: Optional[Iterable[str]] = None) -> int:
    """Run a local benchmark pipeline from a benchmark run spec."""
    parser = argparse.ArgumentParser(description="Run a local benchmark pipeline from a benchmark run spec.")
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_RUNS_ROOT)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--plan-root", type=Path, default=DEFAULT_PLAN_ROOT)
    parser.add_argument("--work-root", type=Path, default=DEFAULT_WORK_ROOT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        run_dir = run_benchmark(
            output_root=args.output_root,
            spec_path=args.spec,
            progress_stream=sys.stderr,
            jobs=args.jobs,
            run_id=args.run_id,
            plan_root=args.plan_root,
            work_root=args.work_root,
            force=args.force,
            allow_missing=args.allow_missing,
        )
    except ValueError as exc:
        print(f"benchmark run failed: {exc}", file=sys.stderr)
        return 2
    print(run_dir)
    return 0


def _run_phase(
    *,
    phase: str,
    rows: tuple[InstancePlanRow, ...] | tuple[TrialPlanRow, ...],
    jobs: int,
    worker: Callable[[Path, int, bool], Path],
    plan_dir: Path,
    force: bool,
    progress_stream: TextIO | None,
) -> None:
    """Run one pipeline phase either sequentially or with a process pool."""
    if not rows:
        return
    if jobs == 1:
        for completed, row in enumerate(rows, start=1):
            worker(plan_dir, row.index, force)
            _emit_progress(progress_stream, f"{phase}: completed {completed}/{len(rows)}")
        return

    with ProcessPoolExecutor(max_workers=jobs) as executor:
        futures = {
            executor.submit(worker, plan_dir, row.index, force): row.index
            for row in rows
        }
        completed = 0
        for future in as_completed(futures):
            index = futures[future]
            try:
                future.result()
            except Exception as exc:
                raise ValueError(f"{phase} failed for index {index}: {exc}") from exc
            completed += 1
            _emit_progress(progress_stream, f"{phase}: completed {completed}/{len(rows)}")


def _run_index_phase(
    *,
    phase: str,
    indices: tuple[int, ...],
    jobs: int,
    worker: Callable[[Path, int, bool], object],
    plan_dir: Path,
    force: bool,
    progress_stream: TextIO | None,
) -> None:
    """Run one pipeline phase over synthetic 1-based task indices."""
    if not indices:
        return
    if jobs == 1:
        for completed, index in enumerate(indices, start=1):
            worker(plan_dir, index, force)
            _emit_progress(progress_stream, f"{phase}: completed {completed}/{len(indices)}")
        return

    with ProcessPoolExecutor(max_workers=jobs) as executor:
        futures = {
            executor.submit(worker, plan_dir, index, force): index
            for index in indices
        }
        completed = 0
        for future in as_completed(futures):
            index = futures[future]
            try:
                future.result()
            except Exception as exc:
                raise ValueError(f"{phase} failed for index {index}: {exc}") from exc
            completed += 1
            _emit_progress(progress_stream, f"{phase}: completed {completed}/{len(indices)}")


def _run_instance_generation_job(plan_dir: Path, index: int, force: bool) -> Path:
    """Run one planned instance generation row for the local orchestrator."""
    return run_instance_generation(plan_dir=plan_dir, index=index, force=force)


def _run_instance_sequence_generation_job(plan_dir: Path, index: int, force: bool) -> list[Path]:
    """Run one planned instance generation sequence for the local orchestrator."""
    return run_instance_sequence_generation(plan_dir=plan_dir, index=index, force=force)


def _run_trial_job(plan_dir: Path, index: int, force: bool) -> Path:
    """Run one planned trial row for the local orchestrator."""
    return run_trial(plan_dir=plan_dir, index=index, force=force)


def _ensure_instance_generation_succeeded(
    *,
    work_root: Path,
    rows: tuple[InstancePlanRow, ...],
) -> None:
    """Stop the pipeline when planned instances were not produced successfully."""
    failures: list[str] = []
    for row in rows:
        result_path = instance_result_path(work_root, row.index)
        if not result_path.exists():
            failures.append(f"{row.index}: missing result")
            continue
        result = json.loads(result_path.read_text(encoding="utf-8"))
        status = str(result.get("status"))
        if status not in {"ok", "skipped"}:
            error = result.get("error")
            suffix = f": {error}" if error else ""
            failures.append(f"{row.index}: {status}{suffix}")
    if failures:
        raise ValueError("instance generation did not complete successfully: " + "; ".join(failures))


def _instance_preparation_summary(*, work_root: Path, rows: tuple[InstancePlanRow, ...]) -> str:
    """Build a user-facing summary for generated vs reused benchmark instances."""
    generated = 0
    reused = 0
    invalid = 0
    errors = 0
    for row in rows:
        result_path = instance_result_path(work_root, row.index)
        if not result_path.exists():
            errors += 1
            continue
        result = json.loads(result_path.read_text(encoding="utf-8"))
        status = str(result.get("status"))
        if status == "skipped" and result.get("generated") is False:
            reused += 1
        elif status == "ok" and result.get("generated") is True:
            generated += 1
        elif status == "invalid":
            invalid += 1
        elif status == "error":
            errors += 1
    return (
        "Instance preparation summary: "
        f"reused existing={reused}, generated new={generated}, invalid={invalid}, errors={errors}"
    )


def _instance_preparation_details(*, work_root: Path, rows: tuple[InstancePlanRow, ...]) -> tuple[str, ...]:
    """Build per-instance preparation lines for generated vs reused benchmark instances."""
    lines: list[str] = []
    for row in rows:
        result_path = instance_result_path(work_root, row.index)
        if not result_path.exists():
            lines.append(f"instance preparation: missing-result {row.instance_id} -> {row.instance_path}")
            continue
        result = json.loads(result_path.read_text(encoding="utf-8"))
        status = str(result.get("status"))
        generated = result.get("generated")
        if status == "skipped" and generated is False:
            action = "reused"
        elif status == "ok" and generated is True:
            action = "generated"
        else:
            action = status
        lines.append(f"instance preparation: {action} {row.instance_id} -> {row.instance_path}")
    return tuple(lines)


def _cleanup_successful_work_dirs(*, plan_dir: Path, work_root: Path, progress_stream: TextIO | None) -> None:
    """Remove isolated plan/work artifacts after a complete successful benchmark run."""
    for path in (work_root, plan_dir):
        if path.exists():
            shutil.rmtree(path)
            _emit_progress(progress_stream, f"Cleaned benchmark temporary directory: {path}")


def _emit_progress(progress_stream: TextIO | None, message: str) -> None:
    if progress_stream is None:
        return
    print(message, file=progress_stream, flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
