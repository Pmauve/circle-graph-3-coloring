from time import perf_counter
from typing import Any, Mapping, Optional

import networkx as nx

from three_col_circle_code.sat.baseline import (
    LEGACY_PYSMT_MSAT,
    PYSAT_CADICAL,
    PYSAT_KISSAT404,
    solve_3color_baseline,
)
from three_col_circle_code.solvers.common import (
    SOLVER_STATUS_ERROR,
    SOLVER_STATUS_OK,
    SolverResult,
)


SAT_BASELINE_SOLVER = "sat-baseline"


def available_sat_solver_backends() -> tuple[str, ...]:
    """Return the supported SAT baseline backends."""
    return (LEGACY_PYSMT_MSAT, PYSAT_CADICAL, PYSAT_KISSAT404)


def solve_sat_solver(
    graph: nx.Graph,
    *,
    backend: str = LEGACY_PYSMT_MSAT,
    params: Optional[Mapping[str, Any]] = None,
) -> SolverResult:
    """Run the SAT baseline through the shared solver-core result contract."""
    requested_params = dict(params or {})
    try:
        started_at = perf_counter()
        result = solve_3color_baseline(graph, backend=backend)
        wall_time_s = perf_counter() - started_at
    except Exception as exc:
        return SolverResult(
            solver=SAT_BASELINE_SOLVER,
            backend=backend,
            status=SOLVER_STATUS_ERROR,
            wall_time_s=None,
            core_time_s=None,
            is_colorable=None,
            n_vertices=graph.number_of_nodes(),
            m_edges=graph.number_of_edges(),
            details={"requested_params": requested_params},
            error=str(exc),
        )

    return SolverResult(
        solver=SAT_BASELINE_SOLVER,
        backend=result.backend,
        status=SOLVER_STATUS_OK,
        wall_time_s=wall_time_s,
        core_time_s=result.elapsed_time,
        is_colorable=result.is_sat,
        n_vertices=result.n_vertices,
        m_edges=result.m_edges,
        details={
            "requested_params": requested_params,
            "core_time_source": result.elapsed_time_source,
        },
        error=None,
    )
