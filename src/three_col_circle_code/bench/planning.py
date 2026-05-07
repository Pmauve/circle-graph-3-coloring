import platform
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

from three_col_circle_code.bench.results import MANIFEST_FILENAME, normalize_run_label
from three_col_circle_code.bench.specs import (
    InstanceRequest,
    RunSpec,
    load_run_spec,
)
from three_col_circle_code.instances.model import bucket_for_n
from three_col_circle_code.solvers.common import SolverConfig
from three_col_circle_code.solvers.sat import PYSAT_KISSAT404, SAT_BASELINE_SOLVER

RUN_SPEC_FILENAME = "spec.json"


def load_spec_for_run(spec_path: Path) -> tuple[str, RunSpec]:
    return load_run_spec(spec_path)


def prepare_run_directory(
    *,
    output_root: Path,
    spec_source: str,
    run_id: str,
) -> Path:
    run_dir = Path(output_root) / normalize_run_label(run_id)
    if run_dir.exists():
        if not run_dir.is_dir():
            raise ValueError(f"run path {run_dir} exists but is not a directory")
    else:
        run_dir.mkdir(parents=True, exist_ok=False)

    spec_copy_path = run_dir / RUN_SPEC_FILENAME
    if spec_copy_path.exists():
        existing_source = spec_copy_path.read_text(encoding="utf-8")
        if existing_source != spec_source:
            raise ValueError("existing run_id refers to a run directory with a different benchmark spec")
    else:
        spec_copy_path.write_text(spec_source, encoding="utf-8")
    return run_dir


def resolve_existing_instance_path(
    *,
    instance_pool_root: Path,
    request: InstanceRequest,
) -> tuple[Optional[Path], Optional[str]]:
    for instance_id, id_kind in _candidate_instance_ids(request):
        flat_instance_path = Path(instance_pool_root) / f"{instance_id}.col"
        if flat_instance_path.exists():
            return flat_instance_path, f"flat-{id_kind}"

        nested_instance_path = (
            Path(instance_pool_root)
            / request.family
            / bucket_for_n(request.n)
            / f"{instance_id}.col"
        )
        if nested_instance_path.exists():
            return nested_instance_path, f"nested-{id_kind}"

        family_root = Path(instance_pool_root) / request.family
        for candidate_path in sorted(family_root.glob(f"*/{instance_id}.col")):
            if candidate_path.exists():
                return candidate_path, f"nested-any-bucket-{id_kind}"
    return None, None


def expected_instance_path(
    *,
    instance_pool_root: Path,
    request: InstanceRequest,
) -> Path:
    return (
        Path(instance_pool_root)
        / request.family
        / bucket_for_n(request.n)
        / f"{request.instance_id}.col"
    )


def _candidate_instance_ids(request: InstanceRequest) -> tuple[tuple[str, str], ...]:
    legacy_id = f"{request.family}-n{request.n:04d}-seed{request.seed}"
    if legacy_id == request.instance_id:
        return ((request.instance_id, "canonical"),)
    return (
        (request.instance_id, "canonical"),
        (legacy_id, "legacy"),
    )


def build_run_manifest(
    *,
    run_id: str,
    run_spec: RunSpec,
    created_at: Optional[str],
    environment: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "created_at": created_at or datetime.now(UTC).isoformat(),
        "spec_filename": RUN_SPEC_FILENAME,
        "instance_pool_root": str(run_spec.instance_pool_root),
        "instance_requests": [
            {
                "instance_id": request.instance_id,
                "family": request.family,
                "n": request.n,
                "seed": request.seed,
                "num_colors": request.num_colors,
                "sequence_id": request.sequence_id,
            }
            for request in run_spec.instance_requests
        ],
        "solvers": [solver_manifest_entry(config) for config in run_spec.solver_configs],
        "n_instances": len(run_spec.instance_requests),
        "n_trials": len(run_spec.instance_requests) * len(run_spec.solver_configs),
        "n_tasks": len(run_spec.instance_requests) * len(run_spec.solver_configs),
        "repetitions": run_spec.repetitions,
        "warmup_repetitions": run_spec.warmup_repetitions,
        "environment": environment or {},
    }


def solver_manifest_entry(config: SolverConfig) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "solver": config.solver,
        "backend": config.backend,
        "target": config.target,
        "params": dict(config.params),
    }
    if config.label is not None:
        entry["label"] = config.label
    return entry


def validate_run_environment(run_spec: RunSpec) -> None:
    system_name = platform.system()
    for solver_config in run_spec.solver_configs:
        if (
            system_name == "Windows"
            and solver_config.solver == SAT_BASELINE_SOLVER
            and solver_config.backend == PYSAT_KISSAT404
        ):
            raise ValueError(
                "SAT backend 'pysat-kissat404' is not supported on Windows; "
                "use WSL/Linux or remove it from the run spec"
            )
