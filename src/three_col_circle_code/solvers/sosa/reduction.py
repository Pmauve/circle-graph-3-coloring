from collections import deque

from three_col_circle_code.solvers.sosa.geometry import SosaGeometry
from three_col_circle_code.solvers.sosa.mask_ops import iter_mask_indices, mask_is_singleton
from three_col_circle_code.solvers.sosa.types import (
    RrExhaustionResult,
    SosaSearchState,
    SosaStats,
)


def apply_rr_step(
    *,
    geometry: SosaGeometry,
    vertex_index: int,
    stats: SosaStats,
    active_vertices_mask: int,
    allowed_color_masks: list[int],
    singleton_queue: deque[int] | None = None,
) -> int | None:
    """Apply one step of the paper's Reduction Rule (RR).

    SOSA Section 3.1 defines RR as:
    1. choose a vertex `v` with `|S(v)| = 1`,
    2. delete `v` from the instance,
    3. remove v's unique color from every neighbor list.

    The step mutates `allowed_color_masks` in place and returns the next
    active-vertices mask. Returning `None` means RR derived an empty list.
    """
    vertex_bit = 1 << vertex_index
    if not (active_vertices_mask & vertex_bit):
        raise ValueError("RR requires an active vertex")
    color_mask = allowed_color_masks[vertex_index]
    if not mask_is_singleton(color_mask):
        raise ValueError("RR requires a singleton color list")

    next_active_vertices_mask = active_vertices_mask & ~vertex_bit
    stats.rr_steps += 1

    for neighbor_index in geometry.neighbor_indices[vertex_index]:
        if not (next_active_vertices_mask & (1 << neighbor_index)):
            continue
        updated_mask = allowed_color_masks[neighbor_index] & ~color_mask
        if updated_mask == allowed_color_masks[neighbor_index]:
            continue
        if updated_mask == 0:
            return None
        allowed_color_masks[neighbor_index] = updated_mask
        if singleton_queue is not None and mask_is_singleton(updated_mask):
            singleton_queue.append(neighbor_index)

    return next_active_vertices_mask


def apply_rr_exhaustively(
    *,
    geometry: SosaGeometry,
    state: SosaSearchState,
    stats: SosaStats,
) -> RrExhaustionResult | None:
    """Apply RR repeatedly until no active vertex has a singleton list."""
    active_vertices_mask = state.active_vertices_mask
    allowed_color_masks = list(state.allowed_color_masks)
    fixed_colors: list[tuple[int, int]] = []
    queue: deque[int] = deque(
        vertex_index
        for vertex_index in iter_mask_indices(active_vertices_mask)
        if mask_is_singleton(allowed_color_masks[vertex_index])
    )

    while queue:
        vertex_index = queue.popleft()
        vertex_bit = 1 << vertex_index
        if not (active_vertices_mask & vertex_bit):
            continue
        color_mask = allowed_color_masks[vertex_index]
        if color_mask == 0:
            return None
        if not mask_is_singleton(color_mask):
            continue

        next_active_vertices_mask = apply_rr_step(
            geometry=geometry,
            vertex_index=vertex_index,
            stats=stats,
            active_vertices_mask=active_vertices_mask,
            allowed_color_masks=allowed_color_masks,
            singleton_queue=queue,
        )
        if next_active_vertices_mask is None:
            return None
        active_vertices_mask = next_active_vertices_mask
        fixed_colors.append((vertex_index, color_mask))

    return RrExhaustionResult(
        state=SosaSearchState(
            active_vertices_mask=active_vertices_mask,
            allowed_color_masks=tuple(allowed_color_masks),
        ),
        fixed_colors=tuple(sorted(fixed_colors)),
    )
