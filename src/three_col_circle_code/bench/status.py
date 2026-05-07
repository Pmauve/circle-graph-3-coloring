import argparse
import json
from collections import Counter
from pathlib import Path
import sys
from typing import Any, Iterable, Optional

from three_col_circle_code.bench.plan_io import (
    instance_result_path,
    load_instance_plan,
    load_plan_manifest,
    load_trial_plan,
    trial_result_path,
)


def build_benchmark_status(
    *,
    plan_dir: Path,
    work_root: Optional[Path] = None,
) -> dict[str, Any]:
    """Build a compact status summary for planned benchmark tasks."""
    resolved_plan_dir = Path(plan_dir)
    manifest = load_plan_manifest(resolved_plan_dir)
    resolved_work_root = Path(work_root) if work_root is not None else Path(str(manifest["work_root"]))
    instances = load_instance_plan(resolved_plan_dir)
    trials = load_trial_plan(resolved_plan_dir, instances=instances)
    instance_status = _summarize_results(
        indices=(row.index for row in instances),
        result_path_for_index=lambda index: instance_result_path(resolved_work_root, index),
        success_statuses={"ok", "skipped"},
    )
    trial_status = _summarize_results(
        indices=(row.index for row in trials),
        result_path_for_index=lambda index: trial_result_path(resolved_work_root, index),
        success_statuses={"ok"},
    )
    return {
        "run_id": str(manifest.get("run_id", resolved_plan_dir.name)),
        "plan_dir": str(resolved_plan_dir),
        "work_root": str(resolved_work_root),
        "instances": instance_status,
        "trials": trial_status,
        "ready_for_trials": instance_status["n_success"] == instance_status["total"],
        "ready_for_merge": trial_status["n_success"] == trial_status["total"],
    }


def main(argv: Optional[Iterable[str]] = None) -> int:
    """Print status for a benchmark plan and its task outputs."""
    parser = argparse.ArgumentParser(description="Print status for benchmark task outputs.")
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, default=None)
    parser.add_argument("--fail-on-incomplete", action="store_true")
    parser.add_argument("--require-ready-for-trials", action="store_true")
    parser.add_argument("--require-ready-for-merge", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        status = build_benchmark_status(plan_dir=args.plan_dir, work_root=args.work_root)
    except ValueError as exc:
        print(f"benchmark status failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(status, indent=2, sort_keys=True))
    if args.require_ready_for_trials and not status["ready_for_trials"]:
        return 1
    if (args.fail_on_incomplete or args.require_ready_for_merge) and not status["ready_for_merge"]:
        return 1
    return 0


def _summarize_results(
    *,
    indices: Iterable[int],
    result_path_for_index: Any,
    success_statuses: set[str],
) -> dict[str, Any]:
    """Summarize result JSON files for a set of planned task indices."""
    materialized_indices = tuple(indices)
    counts: Counter[str] = Counter()
    missing_indices: list[int] = []
    failed_indices: list[int] = []
    for index in materialized_indices:
        path = result_path_for_index(index)
        if not path.exists():
            counts["missing"] += 1
            missing_indices.append(index)
            continue
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
            status = str(row.get("status", "unknown"))
        except (json.JSONDecodeError, OSError):
            status = "unreadable"
        counts[status] += 1
        if status not in success_statuses:
            failed_indices.append(index)
    n_success = sum(counts.get(status, 0) for status in success_statuses)
    return {
        "total": len(materialized_indices),
        "n_success": n_success,
        "counts": dict(sorted(counts.items())),
        "missing_indices": missing_indices,
        "failed_indices": failed_indices,
    }


if __name__ == "__main__":
    raise SystemExit(main())
