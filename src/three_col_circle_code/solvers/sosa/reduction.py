from collections import deque

from three_col_circle_code.solvers.sosa.geometry import SosaGeometry
from three_col_circle_code.solvers.sosa.mask_ops import iter_mask_indices, mask_is_singleton
from three_col_circle_code.solvers.sosa.types import (
    RrExhaustionResult,
    SosaSearchState,
    SosaStats,
    merge_fixed_colors,
)


def apply_rr_step(
    *,
    geometry: SosaGeometry,
    state: SosaSearchState,
    vertex_index: int,
    stats: SosaStats,
) -> RrExhaustionResult | None:
    """Apply one step of the paper's Reduction Rule (RR).

    SOSA Section 3.1 defines RR as:
    1. choose a vertex `v` with `|S(v)| = 1`,
    2. delete `v` from the instance,
    3. remove v's unique color from every neighbor list.
    """
    if not state.is_active(vertex_index):
        raise ValueError("RR requires an active vertex")
    color_mask = state.allowed_color_masks[vertex_index]
    if not mask_is_singleton(color_mask):
        raise ValueError("RR requires a singleton color list")

    active_vertices_mask = state.active_vertices_mask & ~(1 << vertex_index)
    allowed_color_masks = list(state.allowed_color_masks)
    stats.rr_steps += 1

    for neighbor_index in geometry.neighbor_indices[vertex_index]:
        if not (active_vertices_mask & (1 << neighbor_index)):
            continue
        updated_mask = allowed_color_masks[neighbor_index] & ~color_mask
        if updated_mask == allowed_color_masks[neighbor_index]:
            continue
        if updated_mask == 0:
            return None
        allowed_color_masks[neighbor_index] = updated_mask

    return RrExhaustionResult(
        state=SosaSearchState(
            active_vertices_mask=active_vertices_mask,
            allowed_color_masks=tuple(allowed_color_masks),
        ),
        fixed_colors=((vertex_index, color_mask),),
    )


def apply_rr_exhaustively(
    *,
    geometry: SosaGeometry,
    state: SosaSearchState,
    stats: SosaStats,
) -> RrExhaustionResult | None:
    """Apply RR repeatedly until no active vertex has a singleton list."""
    current_state: SosaSearchState = state
    fixed_colors = ()
    queue: deque[int] = deque(
        vertex_index
        for vertex_index in iter_mask_indices(current_state.active_vertices_mask)
        if mask_is_singleton(current_state.allowed_color_masks[vertex_index])
    )

    while queue:
        vertex_index = queue.popleft()
        if not current_state.is_active(vertex_index):
            continue
        color_mask = current_state.allowed_color_masks[vertex_index]
        if color_mask == 0:
            return None
        if not mask_is_singleton(color_mask):
            continue

        rr_step_result = apply_rr_step(
            geometry=geometry,
            state=current_state,
            vertex_index=vertex_index,
            stats=stats,
        )
        if rr_step_result is None:
            return None
        current_state = rr_step_result.state
        fixed_colors = merge_fixed_colors(fixed_colors, rr_step_result.fixed_colors)

        for neighbor_index in geometry.neighbor_indices[vertex_index]:
            if not current_state.is_active(neighbor_index):
                continue
            neighbor_mask = current_state.allowed_color_masks[neighbor_index]
            if neighbor_mask == 0:
                return None
            if mask_is_singleton(neighbor_mask):
                queue.append(neighbor_index)

    return RrExhaustionResult(state=current_state, fixed_colors=fixed_colors)
