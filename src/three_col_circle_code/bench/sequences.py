from pathlib import Path
from typing import Any, Optional

from three_col_circle_code.bench.plan_io import (
    load_instance_plan,
    load_trial_plan,
)


def native_sequence_groups(rows: tuple[Any, ...]) -> list[tuple[Any, ...]]:
    """Group native compact-circle instance rows by one growable trajectory."""
    candidates = [
        row
        for row in rows
        if Path(row.instance_path).suffix == ".circle" and getattr(row, "sequence_id", None) is not None
    ]
    grouped: dict[str, list[Any]] = {}
    for row in candidates:
        grouped.setdefault(str(row.sequence_id), []).append(row)
    groups: list[tuple[Any, ...]] = []
    for group_rows in grouped.values():
        ordered = tuple(sorted(group_rows, key=lambda row: row.n))
        if len(ordered) > 1:
            sequence_bounds(ordered)
        groups.append(ordered)
    return sorted(groups, key=lambda group: min(row.index for row in group))


def load_native_sequence_groups(plan_dir: Path) -> list[tuple[Any, ...]]:
    """Load the instance plan and return native sequence groups."""
    return native_sequence_groups(load_instance_plan(plan_dir))


def select_native_sequence_group(plan_dir: Path, index: int) -> tuple[Any, ...]:
    """Return the 1-based native sequence group from a benchmark plan."""
    groups = load_native_sequence_groups(plan_dir)
    if index < 1 or index > len(groups):
        raise ValueError(f"instance sequence plan does not contain index {index}")
    return groups[index - 1]


def sequence_bounds(rows: tuple[Any, ...]) -> tuple[int, int, int]:
    """Return start, stop, and step for an arithmetic sequence of instance n values."""
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


def trial_rows_by_instance_index(
    plan_dir: Path,
    *,
    instances: Optional[tuple[Any, ...]] = None,
) -> dict[int, tuple[Any, ...]]:
    """Group trial rows by the instance-plan row they use."""
    instance_rows = load_instance_plan(plan_dir) if instances is None else instances
    instance_index_by_id = {row.instance_id: row.index for row in instance_rows}
    grouped: dict[int, list[Any]] = {}
    for trial in load_trial_plan(plan_dir, instances=instance_rows):
        instance_index = instance_index_by_id[trial.instance_id]
        grouped.setdefault(instance_index, []).append(trial)
    return {index: tuple(rows) for index, rows in grouped.items()}
