"""Theorem 3.1 recursive SOSA solver.

Paper mapping:
- the current search state represents the active list-coloring instance `I`,
- `iter_lemma_33_family(...)` enumerates the fully-separated family `F`,
- `I_L(P)` and `I_R(P)` are built by restricting the active state to one arc.
"""

from collections.abc import Mapping
from time import perf_counter
from typing import Any, Optional

import networkx as nx

from three_col_circle_code.solvers.common import (
    SOLVER_STATUS_ERROR,
    SOLVER_STATUS_OK,
    SolverResult,
)
from three_col_circle_code.solvers.sosa.arc_ops import restrict_state_to_arc
from three_col_circle_code.solvers.sosa.base_case import (
    BaseCaseResult,
    solve_base_case_backtracking,
    solve_base_case_sat,
)
from three_col_circle_code.solvers.sosa.colors import mask_to_names
from three_col_circle_code.solvers.sosa.config import SosaConfig
from three_col_circle_code.solvers.sosa.geometry import SosaGeometry
from three_col_circle_code.solvers.sosa.lemma_38 import iter_lemma_33_family
from three_col_circle_code.solvers.sosa.types import (
    FullySeparatedInstance,
    SosaSearchState,
    SosaStats,
    VertexColoring,
    fixed_colors_to_dict,
)


SOSA_3_COL_EXACT_SOLVER = "sosa-3-col-exact"
SOSA_K_COL_HEURISTIC_SOLVER = "sosa-k-col-heuristic"
IMPLEMENTATION_STATUS = "paper-faithful-v1"


def solve_sosa_3_col_exact(
    graph: nx.Graph,
    *,
    params: Optional[Mapping[str, Any]] = None,
) -> SolverResult:
    """Run the theorem-backed exact 3-color SOSA solver.

    Precondition:
    - `graph` must already be a valid canonical chord-annotated
      circle graph.
    """
    return _solve_sosa(
        graph,
        solver=SOSA_3_COL_EXACT_SOLVER,
        params=params,
        validate_config=_validate_sosa_3_col_exact_config,
    )


def solve_sosa_k_col_heuristic(
    graph: nx.Graph,
    *,
    params: Optional[Mapping[str, Any]] = None,
) -> SolverResult:
    """Run experimental SOSA branching with a k-color base-case check."""
    return _solve_sosa(
        graph,
        solver=SOSA_K_COL_HEURISTIC_SOLVER,
        params=params,
        validate_config=_validate_sosa_k_col_heuristic_config,
    )


def _solve_sosa(
    graph: nx.Graph,
    *,
    solver: str,
    params: Optional[Mapping[str, Any]],
    validate_config: Any,
) -> SolverResult:
    """Run one validated SOSA variant on a canonical circle-graph instance."""
    try:
        config = SosaConfig.from_mapping(params)
        validate_config(config)
    except Exception as exc:
        return _error_result(
            graph=graph,
            solver=solver,
            config_dict=None,
            stats=SosaStats(),
            error=f"invalid SOSA parameters: {exc}",
        )

    stats = SosaStats()
    started_at = perf_counter()
    geometry = SosaGeometry.from_graph(graph)
    initial_state = SosaSearchState.initial(n_vertices=geometry.n_vertices)
    solve_result = _solve_state_recursively(
        geometry=geometry,
        state=initial_state,
        config=config,
        stats=stats,
        depth=0,
    )
    return SolverResult(
        solver=solver,
        backend=None,
        status=SOLVER_STATUS_OK,
        wall_time_s=perf_counter() - started_at,
        is_colorable=solve_result.is_colorable,
        n_vertices=geometry.n_vertices,
        m_edges=geometry.m_edges,
        details=_result_details(
            config_dict=config.to_dict(),
            stats=stats,
            geometry=geometry,
            witness=solve_result.witness,
        ),
        error=None,
    )


def _solve_state_recursively(
    *,
    geometry: SosaGeometry,
    state: SosaSearchState,
    config: SosaConfig,
    stats: SosaStats,
    depth: int,
) -> BaseCaseResult:
    """Run ALG-3-Color-Circle-Graph on one list-coloring subinstance `I`."""
    stats.solver_calls += 1
    stats.record_depth(depth)

    # Theorem 3.1, Step 1.
    if state.n_active_vertices <= config.base_case_n:
        return _solve_base_case(
            geometry=geometry,
            state=state,
            config=config,
            stats=stats,
            depth=depth,
        )

    # Theorem 3.1, Step 2.
    for full_instance in iter_lemma_33_family(
        geometry=geometry,
        state=state,
        stats=stats,
    ):
        # Theorem 3.1, Step 3: recurse on I_L(P) and I_R(P).
        child_instances = _ordered_child_subinstances(
            geometry=geometry,
            full_instance=full_instance,
        )
        child_results: list[BaseCaseResult] = []
        branch_failed = False
        for child_state in child_instances:
            child_result = _solve_state_recursively(
                geometry=geometry,
                state=child_state,
                config=config,
                stats=stats,
                depth=depth + 1,
            )
            if not child_result.is_colorable:
                branch_failed = True
                break
            child_results.append(child_result)
        if not branch_failed:
            if any(child_result.witness is None for child_result in child_results):
                return BaseCaseResult(is_colorable=True, witness=None)
            child_witnesses = [child_result.witness for child_result in child_results]
            return BaseCaseResult(
                is_colorable=True,
                witness=_merge_vertex_colorings(
                    fixed_colors_to_dict(full_instance.fixed_colors),
                    *child_witnesses,
                ),
            )
    return BaseCaseResult(is_colorable=False, witness=None)


def _solve_base_case(
    *,
    geometry: SosaGeometry,
    state: SosaSearchState,
    config: SosaConfig,
    stats: SosaStats,
    depth: int,
) -> BaseCaseResult:
    """Dispatch the exact base-case solver configured for SOSA."""
    if config.base_case_algorithm == "sat":
        return solve_base_case_sat(
            geometry=geometry,
            state=state,
            stats=stats,
            depth=depth,
            num_colors=config.num_colors,
        )
    return solve_base_case_backtracking(
        geometry=geometry,
        state=state,
        stats=stats,
        depth=depth,
        num_colors=config.num_colors,
        produce_witness=config.produce_witness,
    )


def _ordered_child_subinstances(
    *,
    geometry: SosaGeometry,
    full_instance: FullySeparatedInstance,
) -> tuple[SosaSearchState, SosaSearchState]:
    """Return I_L(P) and I_R(P) ordered by the fixed smaller-first convention."""
    left_state = restrict_state_to_arc(
        geometry=geometry,
        state=full_instance.state,
        partition=full_instance.partition,
        arc_name="L",
    )
    right_state = restrict_state_to_arc(
        geometry=geometry,
        state=full_instance.state,
        partition=full_instance.partition,
        arc_name="R",
    )
    left_child = (left_state.n_active_vertices, 0, left_state)
    right_child = (right_state.n_active_vertices, 1, right_state)
    ordered_children = sorted((left_child, right_child), key=lambda item: (item[0], item[1]))
    return ordered_children[0][2], ordered_children[1][2]


def _merge_vertex_colorings(*colorings: Mapping[int, int]) -> VertexColoring:
    """Merge disjoint or identical partial colorings into one map."""
    merged: VertexColoring = {}
    for coloring in colorings:
        for vertex_index, color_mask in coloring.items():
            previous = merged.get(vertex_index)
            if previous is not None and previous != color_mask:
                raise AssertionError("conflicting witness assignments")
            merged[vertex_index] = color_mask
    return merged


def _error_result(
    *,
    graph: nx.Graph,
    solver: str,
    config_dict: Optional[dict[str, Any]],
    stats: SosaStats,
    error: str,
) -> SolverResult:
    """Build a standardized SOSA error result."""
    details = _result_details(config_dict=config_dict, stats=stats, geometry=None, witness=None)
    return SolverResult(
        solver=solver,
        backend=None,
        status=SOLVER_STATUS_ERROR,
        wall_time_s=None,
        is_colorable=None,
        n_vertices=graph.number_of_nodes(),
        m_edges=graph.number_of_edges(),
        details=details,
        error=error,
    )


def _validate_sosa_3_col_exact_config(config: SosaConfig) -> None:
    if config.num_colors != 3:
        raise ValueError("SOSA exact 3-color solver requires 'num_colors' to be 3")
    if config.base_case_algorithm == "sat" and config.produce_witness:
        raise ValueError("SOSA SAT base-case solver does not support witness output")


def _validate_sosa_k_col_heuristic_config(config: SosaConfig) -> None:
    if config.num_colors < 4:
        raise ValueError("SOSA k-color heuristic solver requires 'num_colors' to be at least 4")
    if config.produce_witness:
        raise ValueError("SOSA k-color heuristic solver does not support witness output")


def _result_details(
    *,
    config_dict: Optional[dict[str, Any]],
    stats: SosaStats,
    geometry: SosaGeometry | None,
    witness: VertexColoring | None,
) -> dict[str, Any]:
    """Return the standardized SOSA details payload."""
    details: dict[str, Any] = {
        "implementation_status": IMPLEMENTATION_STATUS,
        "config": config_dict or {},
    }
    details.update(stats.to_details_dict())
    if geometry is not None and witness is not None:
        details["coloring_by_node"] = _coloring_by_node(geometry=geometry, witness=witness)
    return details


def _coloring_by_node(
    *,
    geometry: SosaGeometry,
    witness: Mapping[int, int],
) -> dict[Any, str]:
    """Convert an internal vertex-index coloring into node-id/color-name form."""
    return {
        geometry.node_ids[vertex_index]: mask_to_names(color_mask)[0]
        for vertex_index, color_mask in sorted(witness.items())
    }
