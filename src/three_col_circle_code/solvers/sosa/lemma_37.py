"""Lemma 3.7 semi-separated family construction.

Paper mapping:
- `partition` is the balanced partition `P`.
- `rotated_partition` is `P̃`.
- `h_lr_mask` and `h_tb_mask` represent `H_LR` and `H_TB`.
"""

from collections.abc import Iterator

from three_col_circle_code.solvers.sosa.arc_ops import chords_between_arcs
from three_col_circle_code.solvers.sosa.geometry import SosaGeometry
from three_col_circle_code.solvers.sosa.lemma_36 import iter_lemma_36_family
from three_col_circle_code.solvers.sosa.partition import CirclePartition
from three_col_circle_code.solvers.sosa.types import (
    SemiSeparatedInstance,
    SosaSearchState,
    SosaStats,
)


def construct_lemma_37_partition(
    *,
    geometry: SosaGeometry,
    state: SosaSearchState,
) -> CirclePartition:
    """Construct the initial balanced circle partition `P` from Lemma 3.7."""
    n_positions = len(geometry.endpoint_owner)
    if state.n_active_vertices == 0:
        return CirclePartition(
            n_endpoints=n_positions,
            left_boundary=0,
            top_boundary=0,
            right_boundary=0,
            bottom_boundary=0,
        )

    base_arc_size = state.n_active_vertices // 2
    remainder = 2 * state.n_active_vertices - 4 * base_arc_size
    arc_sizes = [
        base_arc_size + (1 if arc_index < remainder else 0)
        for arc_index in range(4)
    ]
    active_endpoint_flags = _active_endpoint_flags(geometry=geometry, state=state)

    left_boundary = 0
    top_boundary = _advance_boundary(
        active_endpoint_flags=active_endpoint_flags,
        start_boundary=left_boundary,
        target_active_endpoints=arc_sizes[0],
    )
    right_boundary = _advance_boundary(
        active_endpoint_flags=active_endpoint_flags,
        start_boundary=top_boundary,
        target_active_endpoints=arc_sizes[1],
    )
    bottom_boundary = _advance_boundary(
        active_endpoint_flags=active_endpoint_flags,
        start_boundary=right_boundary,
        target_active_endpoints=arc_sizes[2],
    )
    return CirclePartition(
        n_endpoints=n_positions,
        left_boundary=left_boundary,
        top_boundary=top_boundary,
        right_boundary=right_boundary,
        bottom_boundary=bottom_boundary,
    )


def iter_lemma_37_family(
    *,
    geometry: SosaGeometry,
    state: SosaSearchState,
    stats: SosaStats,
) -> Iterator[SemiSeparatedInstance]:
    """Enumerate the semi-separated family `S` from Lemma 3.7 lazily."""
    stats.lemma_37_calls += 1
    partition = construct_lemma_37_partition(geometry=geometry, state=state)
    rotated_partition = partition.rotate_counterclockwise()

    # Lemma 3.7, Step 2: build H_LR and H_TB on the current subinstance I.
    h_lr_mask = chords_between_arcs(
        geometry=geometry,
        state=state,
        first_partition=partition,
        first_arc_name="L",
        second_arc_name="R",
    )
    h_tb_mask = chords_between_arcs(
        geometry=geometry,
        state=state,
        first_partition=partition,
        first_arc_name="T",
        second_arc_name="B",
    )

    # Lemma 3.7, Step 3.
    seen_structures: set[tuple[SosaSearchState, CirclePartition]] = set()
    for child_result in iter_lemma_36_family(
        geometry=geometry,
        state=state,
        x_vertices_mask=h_lr_mask,
        y_vertices_mask=h_tb_mask,
        stats=stats,
    ):
        if child_result.state.active_vertices_mask & h_lr_mask == 0:
            semi_instance = SemiSeparatedInstance(
                state=child_result.state,
                partition=partition,
                fixed_colors=child_result.fixed_colors,
            )
        elif child_result.state.active_vertices_mask & h_tb_mask == 0:
            semi_instance = SemiSeparatedInstance(
                state=child_result.state,
                partition=rotated_partition,
                fixed_colors=child_result.fixed_colors,
            )
        else:
            raise AssertionError("Lemma 3.6 output must eliminate either H_LR or H_TB")

        structure_key = (semi_instance.state, semi_instance.partition)
        if structure_key not in seen_structures:
            seen_structures.add(structure_key)
            yield semi_instance


def is_semi_separated_instance(
    *,
    geometry: SosaGeometry,
    semi_instance: SemiSeparatedInstance,
) -> bool:
    """Return whether `(I, P)` satisfies the semi-separated invariant."""
    return (
        chords_between_arcs(
            geometry=geometry,
            state=semi_instance.state,
            first_partition=semi_instance.partition,
            first_arc_name="L",
            second_arc_name="R",
        )
        == 0
    )


def _active_endpoint_flags(
    *,
    geometry: SosaGeometry,
    state: SosaSearchState,
) -> tuple[bool, ...]:
    """Return whether each absolute endpoint position belongs to an active chord."""
    return tuple(
        owner_index != -1 and state.is_active(owner_index)
        for owner_index in geometry.endpoint_owner
    )


def _advance_boundary(
    *,
    active_endpoint_flags: tuple[bool, ...],
    start_boundary: int,
    target_active_endpoints: int,
) -> int:
    """Advance one boundary so the preceding arc contains the requested count."""
    if target_active_endpoints == 0:
        return start_boundary

    n_positions = len(active_endpoint_flags)
    current = start_boundary
    remaining = target_active_endpoints
    visited = 0
    while visited < n_positions:
        if active_endpoint_flags[current]:
            remaining -= 1
            if remaining == 0:
                return (current + 1) % n_positions
        current = (current + 1) % n_positions
        visited += 1

    raise AssertionError("failed to place a balanced circle partition")
