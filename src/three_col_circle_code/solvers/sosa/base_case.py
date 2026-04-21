from dataclasses import dataclass

from three_col_circle_code.solvers.sosa.colors import ALL_COLOR_MASK, COLOR_MASK_ORDER
from three_col_circle_code.solvers.sosa.geometry import SosaGeometry
from three_col_circle_code.solvers.sosa.mask_ops import iter_mask_indices
from three_col_circle_code.solvers.sosa.types import SosaSearchState, SosaStats, VertexColoring


@dataclass(frozen=True, slots=True)
class BaseCaseResult:
    """Normalized result shape for one exact SOSA base-case solve."""

    is_colorable: bool
    witness: VertexColoring | None


def solve_base_case_backtracking(
    *,
    geometry: SosaGeometry,
    state: SosaSearchState,
    stats: SosaStats,
    depth: int,
) -> BaseCaseResult:
    """Solve one small list-coloring state exactly with backtracking."""
    stats.base_case_calls += 1
    stats.record_depth(depth)

    active_indices = tuple(iter_mask_indices(state.active_vertices_mask))
    if any(state.allowed_color_masks[index] == 0 for index in active_indices):
        return BaseCaseResult(is_colorable=False, witness=None)

    order = sorted(
        active_indices,
        key=lambda index: _active_degree(
            geometry=geometry,
            state=state,
            vertex_index=index,
        ),
        reverse=True,
    )
    colors: VertexColoring = {}

    def backtrack(position: int) -> VertexColoring | None:
        stats.base_case_search_nodes += 1
        stats.record_depth(depth + position)
        if position == len(order):
            return dict(colors)

        vertex_index = order[position]
        allowed_mask = state.allowed_color_masks[vertex_index]
        used_mask = 0
        for neighbor_index in geometry.neighbor_indices[vertex_index]:
            neighbor_color = colors.get(neighbor_index)
            if neighbor_color is not None:
                used_mask |= neighbor_color
        available_mask = allowed_mask & (ALL_COLOR_MASK ^ used_mask)
        for color_mask in COLOR_MASK_ORDER:
            if not (available_mask & color_mask):
                continue
            colors[vertex_index] = color_mask
            witness = backtrack(position + 1)
            if witness is not None:
                return witness
            del colors[vertex_index]
        return None

    witness = backtrack(0)
    return BaseCaseResult(
        is_colorable=witness is not None,
        witness=witness,
    )


def _active_degree(
    *,
    geometry: SosaGeometry,
    state: SosaSearchState,
    vertex_index: int,
) -> int:
    """Count active neighbors of one vertex in the current search state."""
    return (geometry.adjacency_masks[vertex_index] & state.active_vertices_mask).bit_count()
