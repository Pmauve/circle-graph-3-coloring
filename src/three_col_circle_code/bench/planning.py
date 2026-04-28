import platform
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from three_col_circle_code.bench.results import MANIFEST_FILENAME, normalize_run_label
from three_col_circle_code.bench.specs import (
    InstanceRequest,
    RunSpec,
    canonical_params_json,
    load_run_spec,
)
from three_col_circle_code.generation.random_instances import generate_instance, write_instance
from three_col_circle_code.instances.model import bucket_for_n
from three_col_circle_code.solvers.common import SolverConfig
from three_col_circle_code.solvers.sat import PYSAT_KISSAT404, SAT_BASELINE_SOLVER

RUN_SPEC_FILENAME = "spec.json"


@dataclass(frozen=True)
class BenchmarkTrial:
    instance_request: InstanceRequest
    instance_path: Path
    solver_config: SolverConfig

    @property
    def key(self) -> tuple[str, str, str]:
        return benchmark_trial_key(self)


@dataclass(frozen=True)
class MaterializedInstances:
    paths: dict[str, Path]
    n_found_flat: int
    n_found_nested: int
    n_generated: int


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


def materialize_run_instances(
    run_spec: RunSpec,
    *,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> MaterializedInstances:
    resolved: dict[str, Path] = {}
    n_found_flat = 0
    n_found_nested = 0
    n_generated = 0
    missing_requests = [
        request
        for request in run_spec.instance_requests
        if resolve_existing_instance_path(
            instance_pool_root=run_spec.instance_pool_root,
            request=request,
        )[0] is None
    ]
    if missing_requests and progress_callback is not None:
        progress_callback(f"Generating missing instances ({len(missing_requests)} total)...")
    for request in run_spec.instance_requests:
        instance_path, resolution = resolve_or_generate_instance(
            instance_pool_root=run_spec.instance_pool_root,
            request=request,
        )
        resolved[request.instance_id] = instance_path
        if resolution == "flat":
            n_found_flat += 1
        elif resolution == "nested":
            n_found_nested += 1
        else:
            n_generated += 1
            if progress_callback is not None and _should_emit_generation_progress(
                generated_count=n_generated,
                generated_total=len(missing_requests),
            ):
                progress_callback(f"Generated {n_generated}/{len(missing_requests)} missing instances")
    return MaterializedInstances(
        paths=resolved,
        n_found_flat=n_found_flat,
        n_found_nested=n_found_nested,
        n_generated=n_generated,
    )


def resolve_or_generate_instance(
    *,
    instance_pool_root: Path,
    request: InstanceRequest,
) -> tuple[Path, str]:
    existing_instance_path, existing_resolution = resolve_existing_instance_path(
        instance_pool_root=instance_pool_root,
        request=request,
    )
    if existing_instance_path is not None and existing_resolution is not None:
        return existing_instance_path, existing_resolution

    record = generate_instance(family=request.family, n=request.n, seed=request.seed)
    return write_instance(record, instance_pool_root), "generated"


def resolve_existing_instance_path(
    *,
    instance_pool_root: Path,
    request: InstanceRequest,
) -> tuple[Optional[Path], Optional[str]]:
    flat_instance_path = Path(instance_pool_root) / f"{request.instance_id}.json"
    if flat_instance_path.exists():
        return flat_instance_path, "flat"

    nested_instance_path = expected_instance_path(
        instance_pool_root=instance_pool_root,
        request=request,
    )
    if nested_instance_path.exists():
        return nested_instance_path, "nested"
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
        / f"{request.instance_id}.json"
    )


def iter_benchmark_trials(
    run_spec: RunSpec,
    instance_paths: Mapping[str, Path],
) -> tuple[BenchmarkTrial, ...]:
    trials = [
        BenchmarkTrial(
            instance_request=request,
            instance_path=Path(instance_paths[request.instance_id]),
            solver_config=solver_config,
        )
        for request in run_spec.instance_requests
        for solver_config in run_spec.solver_configs
    ]
    return tuple(
        sorted(
            trials,
            key=lambda trial: (
                trial.instance_request.family,
                trial.instance_request.n,
                trial.instance_request.seed,
                trial.solver_config.target,
                canonical_params_json(trial.solver_config.params),
            ),
        )
    )


def benchmark_trial_key(trial: BenchmarkTrial) -> tuple[str, str, str]:
    return (
        trial.instance_request.instance_id,
        trial.solver_config.target,
        canonical_params_json(trial.solver_config.params),
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
            }
            for request in run_spec.instance_requests
        ],
        "solvers": [solver_manifest_entry(config) for config in run_spec.solver_configs],
        "n_instances": len(run_spec.instance_requests),
        "n_trials": len(run_spec.instance_requests) * len(run_spec.solver_configs),
        "n_tasks": len(run_spec.instance_requests) * len(run_spec.solver_configs),
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


def _should_emit_generation_progress(*, generated_count: int, generated_total: int) -> bool:
    if generated_total < 1:
        return False
    return generated_count in {1, generated_total} or generated_count % 10 == 0
