from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import networkx as nx

from three_col_circle_code.instances.model import InstanceRecord
from three_col_circle_code.instances.io import load_instance
from three_col_circle_code.instances.validate import validate_instance
from three_col_circle_code.solvers.common import SolverConfig, SolverResult
from three_col_circle_code.solvers.sat import (
    SAT_BASELINE_SOLVER,
    available_sat_solver_backends,
    solve_sat_solver,
)
from three_col_circle_code.solvers.sat_native import (
    SAT_3_COL_NATIVE_SOLVER,
    solve_sat_3_col_native_from_path,
)
from three_col_circle_code.solvers.sosa.solver import (
    SOSA_3_COL_EXACT_SOLVER,
    SOSA_K_COL_HEURISTIC_SOLVER,
    solve_sosa_3_col_exact,
    solve_sosa_k_col_heuristic,
)
from three_col_circle_code.solvers.sosa.native import (
    SOSA_3_COL_NATIVE_SOLVER,
    solve_sosa_3_col_native_from_path,
)
from three_col_circle_code.solvers.zykovcolor import (
    ZYKOVCOLOR_SOLVER,
    solve_zykovcolor,
    solve_zykovcolor_path,
)


def available_solver_names() -> tuple[str, ...]:
    """Return the registered solver families."""
    return (
        SAT_BASELINE_SOLVER,
        SAT_3_COL_NATIVE_SOLVER,
        SOSA_3_COL_EXACT_SOLVER,
        SOSA_K_COL_HEURISTIC_SOLVER,
        SOSA_3_COL_NATIVE_SOLVER,
        ZYKOVCOLOR_SOLVER,
    )


def resolve_solver_configs(
    solver_specs: Optional[Sequence[str]] = None,
) -> tuple[SolverConfig, ...]:
    """Expand user-facing solver specs into concrete solver configs."""
    if not solver_specs:
        return tuple(
            SolverConfig(solver=SAT_BASELINE_SOLVER, backend=backend)
            for backend in available_sat_solver_backends()
        )

    resolved: list[SolverConfig] = []
    for spec in solver_specs:
        solver, backend = _parse_solver_spec(spec)
        if solver == SAT_BASELINE_SOLVER and backend is None:
            resolved.extend(
                SolverConfig(solver=SAT_BASELINE_SOLVER, backend=sat_backend)
                for sat_backend in available_sat_solver_backends()
            )
            continue
        _validate_solver_config(solver=solver, backend=backend)
        resolved.append(SolverConfig(solver=solver, backend=backend))
    return tuple(resolved)


def run_solver(
    instance_or_graph: InstanceRecord | nx.Graph,
    config: SolverConfig,
) -> SolverResult:
    """Dispatch one solver-core invocation through the registered solver family."""
    graph = instance_or_graph.graph if isinstance(instance_or_graph, InstanceRecord) else instance_or_graph
    if config.solver == SAT_BASELINE_SOLVER:
        return solve_sat_solver(
            graph,
            backend=config.backend or available_sat_solver_backends()[0],
            params=config.params,
        )
    if config.solver == SAT_3_COL_NATIVE_SOLVER:
        raise ValueError("native SAT solver requires a file path; use run_solver_from_path")
    if config.solver == SOSA_3_COL_EXACT_SOLVER:
        if config.backend is not None:
            raise ValueError("SOSA solver does not support backends")
        return solve_sosa_3_col_exact(graph, params=config.params)
    if config.solver == SOSA_K_COL_HEURISTIC_SOLVER:
        if config.backend is not None:
            raise ValueError("SOSA solver does not support backends")
        return solve_sosa_k_col_heuristic(graph, params=config.params)
    if config.solver == SOSA_3_COL_NATIVE_SOLVER:
        raise ValueError("native SOSA solver requires a file path; use run_solver_from_path")
    if config.solver == ZYKOVCOLOR_SOLVER:
        if config.backend is not None:
            raise ValueError("ZykovColor solver does not support backends")
        return solve_zykovcolor(instance_or_graph, params=config.params)
    raise ValueError(
        f"unsupported solver {config.solver!r}; expected one of {available_solver_names()}"
    )


def run_solver_from_path(
    instance_path: Path,
    config: SolverConfig,
    *,
    validate_instance_artifact: bool = False,
) -> SolverResult:
    """Dispatch one solver invocation from a benchmark instance artifact path."""
    if validate_instance_artifact:
        record = load_instance(instance_path, validate=True)
        report = validate_instance(record.graph, metadata=record.metadata.to_dict())
        if not report.ok:
            errors = [{"code": issue.code, "message": issue.message} for issue in report.errors]
            raise ValueError(f"instance artifact did not validate: {errors}")
    elif config.solver not in (SAT_3_COL_NATIVE_SOLVER, SOSA_3_COL_NATIVE_SOLVER, ZYKOVCOLOR_SOLVER):
        record = load_instance(instance_path, validate=False)
    else:
        record = None

    if config.solver == SAT_3_COL_NATIVE_SOLVER:
        if config.backend is not None:
            raise ValueError("native SAT solver does not support registry backends")
        return solve_sat_3_col_native_from_path(instance_path, params=config.params)
    if config.solver == SOSA_3_COL_NATIVE_SOLVER:
        if config.backend is not None:
            raise ValueError("SOSA solver does not support backends")
        return solve_sosa_3_col_native_from_path(
            instance_path,
            params=config.params,
            validate_instance_artifact=validate_instance_artifact,
        )
    if config.solver == ZYKOVCOLOR_SOLVER:
        if config.backend is not None:
            raise ValueError("ZykovColor solver does not support backends")
        return solve_zykovcolor_path(instance_path, params=config.params)
    if record is None:
        record = load_instance(instance_path, validate=False)
    return run_solver(record, config)


def _parse_solver_spec(spec: str) -> tuple[str, Optional[str]]:
    """Split a solver spec like 'solver' or 'solver:backend'."""
    solver, separator, backend = spec.partition(":")
    if not solver:
        raise ValueError("solver spec must not be empty")
    if separator and not backend:
        raise ValueError(f"solver spec {spec!r} is missing a backend after ':'")
    return solver, backend or None


def _validate_solver_config(*, solver: str, backend: Optional[str]) -> None:
    """Validate a solver/backend pair against the current registry."""
    if solver in (
        SOSA_3_COL_EXACT_SOLVER,
        SOSA_K_COL_HEURISTIC_SOLVER,
        SAT_3_COL_NATIVE_SOLVER,
        SOSA_3_COL_NATIVE_SOLVER,
        ZYKOVCOLOR_SOLVER,
    ):
        if backend is not None:
            raise ValueError(f"{solver} solver does not support backends")
        return
    if solver != SAT_BASELINE_SOLVER:
        raise ValueError(
            f"unsupported solver {solver!r}; expected one of {available_solver_names()}"
        )
    if backend is not None and backend not in available_sat_solver_backends():
        raise ValueError(
            f"unsupported SAT backend {backend!r}; expected one of {available_sat_solver_backends()}"
        )
