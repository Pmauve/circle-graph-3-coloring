from dataclasses import dataclass

from three_col_circle_code.sat.baseline import PYSAT_CADICAL
from three_col_circle_code.sat.pysat_baseline import solve_reduced_list_coloring_cnf
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
    num_colors: int = 3,
    produce_witness: bool = True,
) -> BaseCaseResult:
    """Solve one small list-coloring state exactly with backtracking."""
    stats.base_case_calls += 1
    stats.record_depth(depth)

    active_indices = tuple(iter_mask_indices(state.active_vertices_mask))
    allowed_color_masks = _base_case_allowed_color_masks(
        allowed_color_masks=state.allowed_color_masks,
        num_colors=num_colors,
    )
    if any(allowed_color_masks[index] == 0 for index in active_indices):
        return BaseCaseResult(is_colorable=False, witness=None)

    color_mask_limit = (1 << num_colors) - 1
    color_mask_order = _color_mask_order(num_colors)
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

    def backtrack(position: int) -> VertexColoring | bool | None:
        stats.base_case_search_nodes += 1
        stats.record_depth(depth + position)
        if position == len(order):
            if produce_witness:
                return dict(colors)
            return True

        vertex_index = order[position]
        allowed_mask = allowed_color_masks[vertex_index]
        used_mask = 0
        for neighbor_index in geometry.neighbor_indices[vertex_index]:
            neighbor_color = colors.get(neighbor_index)
            if neighbor_color is not None:
                used_mask |= neighbor_color
        available_mask = allowed_mask & (color_mask_limit ^ used_mask)
        for color_mask in color_mask_order:
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
        witness=witness if produce_witness and isinstance(witness, dict) else None,
    )


def solve_base_case_sat(
    *,
    geometry: SosaGeometry,
    state: SosaSearchState,
    stats: SosaStats,
    depth: int,
    num_colors: int = 3,
    backend: str = PYSAT_CADICAL,
) -> BaseCaseResult:
    """Solve one small list-coloring state exactly with SAT."""
    stats.base_case_calls += 1
    stats.record_depth(depth)

    is_colorable = solve_reduced_list_coloring_cnf(
        active_vertices_mask=state.active_vertices_mask,
        neighbor_indices=geometry.neighbor_indices,
        allowed_color_masks=_base_case_allowed_color_masks(
            allowed_color_masks=state.allowed_color_masks,
            num_colors=num_colors,
        ),
        num_colors=num_colors,
        backend=backend,
    )
    return BaseCaseResult(
        is_colorable=is_colorable,
        witness=None,
    )


def _active_degree(
    *,
    geometry: SosaGeometry,
    state: SosaSearchState,
    vertex_index: int,
) -> int:
    """Count active neighbors of one vertex in the current search state."""
    return (geometry.adjacency_masks[vertex_index] & state.active_vertices_mask).bit_count()


def _base_case_allowed_color_masks(
    *,
    allowed_color_masks: tuple[int, ...],
    num_colors: int,
) -> tuple[int, ...]:
    """Extend SOSA RGB lists with extra k-color choices for base-case checks."""
    if num_colors <= 3:
        return allowed_color_masks
    extra_color_mask = ((1 << num_colors) - 1) & ~ALL_COLOR_MASK
    return tuple(allowed_mask | extra_color_mask for allowed_mask in allowed_color_masks)


def _color_mask_order(num_colors: int) -> tuple[int, ...]:
    if num_colors == 3:
        return COLOR_MASK_ORDER
    return tuple(1 << color_index for color_index in range(num_colors))
