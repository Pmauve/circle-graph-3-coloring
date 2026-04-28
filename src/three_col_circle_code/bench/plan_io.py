import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence


INSTANCES_FILENAME = "instances.jsonl"
TRIALS_FILENAME = "trials.jsonl"
PLAN_MANIFEST_FILENAME = "manifest.json"
PLAN_SPEC_FILENAME = "spec.json"


@dataclass(frozen=True)
class InstancePlanRow:
    index: int
    instance_id: str
    family: str
    n: int
    seed: int
    instance_path: Path

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> "InstancePlanRow":
        _require_fields(row, ("index", "instance_id", "family", "n", "seed", "instance_path"))
        return cls(
            index=int(row["index"]),
            instance_id=str(row["instance_id"]),
            family=str(row["family"]),
            n=int(row["n"]),
            seed=int(row["seed"]),
            instance_path=Path(str(row["instance_path"])),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "instance_id": self.instance_id,
            "family": self.family,
            "n": self.n,
            "seed": self.seed,
            "instance_path": str(self.instance_path),
        }


@dataclass(frozen=True)
class TrialPlanRow:
    index: int
    instance_id: str
    instance_path: Path
    family: str
    n: int
    seed: int
    solver: str
    backend: Optional[str]
    solver_target: str
    solver_params: dict[str, Any] = field(default_factory=dict)
    solver_label: Optional[str] = None

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> "TrialPlanRow":
        _require_fields(
            row,
            (
                "index",
                "instance_id",
                "instance_path",
                "family",
                "n",
                "seed",
                "solver",
                "backend",
                "solver_target",
                "solver_params",
                "solver_label",
            ),
        )
        solver_params = row["solver_params"]
        if not isinstance(solver_params, Mapping):
            raise ValueError("trial plan row field 'solver_params' must be an object")
        solver_label = row["solver_label"]
        return cls(
            index=int(row["index"]),
            instance_id=str(row["instance_id"]),
            instance_path=Path(str(row["instance_path"])),
            family=str(row["family"]),
            n=int(row["n"]),
            seed=int(row["seed"]),
            solver=str(row["solver"]),
            backend=None if row["backend"] is None else str(row["backend"]),
            solver_target=str(row["solver_target"]),
            solver_params=dict(solver_params),
            solver_label=None if solver_label is None else str(solver_label),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "instance_id": self.instance_id,
            "instance_path": str(self.instance_path),
            "family": self.family,
            "n": self.n,
            "seed": self.seed,
            "solver": self.solver,
            "backend": self.backend,
            "solver_target": self.solver_target,
            "solver_params": dict(self.solver_params),
            "solver_label": self.solver_label,
        }


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as outfile:
        for row in rows:
            outfile.write(json.dumps(dict(row), sort_keys=True))
            outfile.write("\n")
    return path


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as infile:
        return [json.loads(line) for line in infile if line.strip()]


def write_plan_manifest(plan_dir: Path, manifest: Mapping[str, Any]) -> Path:
    plan_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = plan_dir / PLAN_MANIFEST_FILENAME
    with manifest_path.open("w", encoding="utf-8") as outfile:
        json.dump(_json_ready(dict(manifest)), outfile, indent=2, sort_keys=True)
        outfile.write("\n")
    return manifest_path


def load_plan_manifest(plan_dir: Path) -> dict[str, Any]:
    manifest_path = Path(plan_dir) / PLAN_MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, Mapping):
        raise ValueError("plan manifest must be a JSON object")
    return dict(manifest)


def write_instance_plan(plan_dir: Path, rows: Iterable[InstancePlanRow]) -> Path:
    materialized = tuple(rows)
    validate_instance_plan(materialized)
    return write_jsonl(Path(plan_dir) / INSTANCES_FILENAME, (row.to_dict() for row in materialized))


def load_instance_plan(plan_dir: Path) -> tuple[InstancePlanRow, ...]:
    rows = tuple(InstancePlanRow.from_mapping(row) for row in read_jsonl(Path(plan_dir) / INSTANCES_FILENAME))
    validate_instance_plan(rows)
    return rows


def write_trial_plan(
    plan_dir: Path,
    rows: Iterable[TrialPlanRow],
    *,
    instances: Iterable[InstancePlanRow],
) -> Path:
    materialized = tuple(rows)
    validate_trial_plan(materialized, instances=tuple(instances))
    return write_jsonl(Path(plan_dir) / TRIALS_FILENAME, (row.to_dict() for row in materialized))


def load_trial_plan(
    plan_dir: Path,
    *,
    instances: Iterable[InstancePlanRow],
) -> tuple[TrialPlanRow, ...]:
    rows = tuple(TrialPlanRow.from_mapping(row) for row in read_jsonl(Path(plan_dir) / TRIALS_FILENAME))
    validate_trial_plan(rows, instances=tuple(instances))
    return rows


def instance_result_path(work_root: Path, index: int) -> Path:
    return _indexed_result_path(Path(work_root) / "instances", index)


def trial_result_path(work_root: Path, index: int) -> Path:
    return _indexed_result_path(Path(work_root) / "trials", index)


def validate_instance_plan(rows: Sequence[InstancePlanRow]) -> None:
    _validate_contiguous_indices(row.index for row in rows)
    seen_instance_ids: set[str] = set()
    for row in rows:
        if row.instance_id in seen_instance_ids:
            raise ValueError(f"instance plan contains duplicate instance id {row.instance_id!r}")
        seen_instance_ids.add(row.instance_id)
        if _path_contains_part(row.instance_path, "benchmark_work"):
            raise ValueError("instance plan paths must point to the canonical instance pool")


def validate_trial_plan(
    rows: Sequence[TrialPlanRow],
    *,
    instances: Sequence[InstancePlanRow],
) -> None:
    _validate_contiguous_indices(row.index for row in rows)
    instance_by_id = {row.instance_id: row for row in instances}
    seen_trial_keys: set[tuple[str, str, str]] = set()
    for row in rows:
        instance = instance_by_id.get(row.instance_id)
        if instance is None:
            raise ValueError(f"trial plan references unknown instance id {row.instance_id!r}")
        if row.instance_path != instance.instance_path:
            raise ValueError(f"trial plan row {row.index} uses an instance_path that differs from instances.jsonl")
        trial_key = (row.instance_id, row.solver_target, json.dumps(row.solver_params, sort_keys=True))
        if trial_key in seen_trial_keys:
            raise ValueError(f"trial plan contains duplicate trial for {row.instance_id!r} and {row.solver_target!r}")
        seen_trial_keys.add(trial_key)


def _indexed_result_path(root: Path, index: int) -> Path:
    if index < 1:
        raise ValueError("result index must be positive")
    return root / f"{index:06d}" / "result.json"


def _validate_contiguous_indices(indices: Iterable[int]) -> None:
    materialized = list(indices)
    expected = list(range(1, len(materialized) + 1))
    if materialized != expected:
        raise ValueError("plan row indices must be contiguous starting at 1")


def _path_contains_part(path: Path, part: str) -> bool:
    return part in {item.lower() for item in path.parts}


def _require_fields(row: Mapping[str, Any], fields: Iterable[str]) -> None:
    missing = [field for field in fields if field not in row]
    if missing:
        raise ValueError("plan row is missing required field(s): " + ", ".join(missing))


def _json_ready(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value
