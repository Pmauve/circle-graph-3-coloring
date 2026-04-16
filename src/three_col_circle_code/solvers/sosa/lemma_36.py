"""Lemma 3.6 helper family construction.

Paper mapping:
- `x_vertices_mask` corresponds to `X`.
- `y_vertices_mask` corresponds to `Y`.
- each yielded result is one RR-reduced subinstance `I′′` in the family `F`.
"""

from collections.abc import Iterator

from three_col_circle_code.solvers.sosa.colors import COLOR_MASK_ORDER
from three_col_circle_code.solvers.sosa.geometry import SosaGeometry
from three_col_circle_code.solvers.sosa.mask_ops import iter_mask_indices
from three_col_circle_code.solvers.sosa.reduction import apply_rr_exhaustively
from three_col_circle_code.solvers.sosa.types import RrExhaustionResult, SosaSearchState, SosaStats


def iter_lemma_36_family(
        *,
        geometry: SosaGeometry,
        state: SosaSearchState,
        x_vertices_mask: int,
        y_vertices_mask: int,
        stats: SosaStats,
) -> Iterator[RrExhaustionResult]:
    """Enumerate the family `F` from Lemma 3.6 lazily."""
    stats.lemma_36_calls += 1

    seen_states: set[SosaSearchState] = set()
    active_x_mask = x_vertices_mask & state.active_vertices_mask
    active_y_mask = y_vertices_mask & state.active_vertices_mask

    # Lemma 3.6, Step 2.
    if not _contains_internal_edge(geometry=geometry, vertices_mask=active_x_mask):
        yield from _iter_monochromatic_branches(
            geometry=geometry,
            state=state,
            vertices_mask=active_x_mask,
            seen_states=seen_states,
            stats=stats,
        )

    # Lemma 3.6, Step 3.
    if not _contains_internal_edge(geometry=geometry, vertices_mask=active_y_mask):
        yield from _iter_monochromatic_branches(
            geometry=geometry,
            state=state,
            vertices_mask=active_y_mask,
            seen_states=seen_states,
            stats=stats,
        )


def _iter_monochromatic_branches(
        *,
        geometry: SosaGeometry,
        state: SosaSearchState,
        vertices_mask: int,
        seen_states: set[SosaSearchState],
        stats: SosaStats,
) -> Iterator[RrExhaustionResult]:
    """Enumerate the RR-reduced monochromatic branches for one side of Lemma 3.6."""
    target_vertices = tuple(iter_mask_indices(vertices_mask))
    for color_mask in COLOR_MASK_ORDER:
        if any(
                not (state.allowed_color_masks[vertex_index] & color_mask)
                for vertex_index in target_vertices
        ):
            continue

        allowed_color_masks = list(state.allowed_color_masks)
        for vertex_index in target_vertices:
            allowed_color_masks[vertex_index] = color_mask

        # This is the intermediate subinstance I′ from Lemma 3.6.
        i_prime = SosaSearchState(
            active_vertices_mask=state.active_vertices_mask,
            allowed_color_masks=tuple(allowed_color_masks),
        )
        # Applying RR exhaustively yields the final state I′′ added to F.
        i_double_prime = apply_rr_exhaustively(
            geometry=geometry,
            state=i_prime,
            stats=stats,
        )
        if i_double_prime is not None and i_double_prime.state not in seen_states:
            seen_states.add(i_double_prime.state)
            yield i_double_prime


def _contains_internal_edge(
        *,
        geometry: SosaGeometry,
        vertices_mask: int,
) -> bool:
    """Return whether the target chord set is not independent."""
    for vertex_index in iter_mask_indices(vertices_mask):
        other_vertices_mask = vertices_mask & ~(1 << vertex_index)
        if geometry.adjacency_masks[vertex_index] & other_vertices_mask:
            return True
    return False
