"""Lemma 3.8 and Lemma 3.3 fully-separated family construction.

Paper mapping:
- `semi_instance` represents `(I, P)`.
- `chosen_arc_name` and `x` correspond to the chosen arc `X` and its size `x`.
- `x_left` and `x_right` correspond to `X_L` and `X_R`.
- `h_left_mask` and `h_right_mask` represent `H_L` and `H_R`.
"""

from collections.abc import Iterator

from three_col_circle_code.solvers.sosa.arc_ops import (
    advance_boundary_inside_arc,
    chords_between_arcs,
    chords_between_partition_arcs,
    count_active_endpoints_in_arc,
)
from three_col_circle_code.solvers.sosa.geometry import SosaGeometry
from three_col_circle_code.solvers.sosa.lemma_36 import iter_lemma_36_family
from three_col_circle_code.solvers.sosa.lemma_37 import iter_lemma_37_family
from three_col_circle_code.solvers.sosa.partition import CirclePartition
from three_col_circle_code.solvers.sosa.types import (
    FullySeparatedInstance,
    SemiSeparatedInstance,
    SosaSearchState,
    SosaStats,
    merge_fixed_colors,
)


def iter_lemma_38_family(
    *,
    geometry: SosaGeometry,
    semi_instance: SemiSeparatedInstance,
    stats: SosaStats,
) -> Iterator[FullySeparatedInstance]:
    """Enumerate the fully-separated family `F` from Lemma 3.8 lazily."""
    stats.lemma_38_calls += 1
    seen_structures: set[tuple[SosaSearchState, CirclePartition]] = set()
    yield from _iter_lemma_38_family_recursive(
        geometry=geometry,
        semi_instance=semi_instance,
        stats=stats,
        seen_structures=seen_structures,
    )


def iter_lemma_33_family(
    *,
    geometry: SosaGeometry,
    state: SosaSearchState,
    stats: SosaStats,
) -> Iterator[FullySeparatedInstance]:
    """Enumerate the fully-separated family `F` from Lemma 3.3 lazily."""
    stats.lemma_33_calls += 1
    seen_structures: set[tuple[SosaSearchState, CirclePartition]] = set()
    for semi_instance in iter_lemma_37_family(geometry=geometry, state=state, stats=stats):
        for full_instance in iter_lemma_38_family(
            geometry=geometry,
            semi_instance=semi_instance,
            stats=stats,
        ):
            structure_key = (full_instance.state, full_instance.partition)
            if structure_key not in seen_structures:
                seen_structures.add(structure_key)
                yield full_instance


def is_fully_separated_instance(
    *,
    geometry: SosaGeometry,
    full_instance: FullySeparatedInstance,
) -> bool:
    """Return whether `(I, P)` satisfies the fully-separated invariant."""
    partition = full_instance.partition
    return (
        partition.top_boundary == partition.right_boundary
        and partition.bottom_boundary == partition.left_boundary
        and chords_between_arcs(
            geometry=geometry,
            state=full_instance.state,
            first_partition=partition,
            first_arc_name="L",
            second_arc_name="R",
        )
        == 0
    )


def _iter_lemma_38_family_recursive(
    *,
    geometry: SosaGeometry,
    semi_instance: SemiSeparatedInstance,
    stats: SosaStats,
    seen_structures: set[tuple[SosaSearchState, CirclePartition]],
) -> Iterator[FullySeparatedInstance]:
    """Run the recursive procedure ALG-Semi-Full from Lemma 3.8."""
    partition = semi_instance.partition
    state = semi_instance.state
    chosen_arc_name, x = _choose_x_arc(geometry=geometry, state=state, partition=partition)

    # Lemma 3.8, Step 3.
    if x == 0:
        full_instance = FullySeparatedInstance(
            state=state,
            partition=_collapse_empty_top_and_bottom(partition=partition),
            fixed_colors=semi_instance.fixed_colors,
        )
        structure_key = (full_instance.state, full_instance.partition)
        if structure_key not in seen_structures:
            seen_structures.add(structure_key)
            yield full_instance
        return

    # Lemma 3.8, Step 4.
    if x == 1:
        next_partition = _partition_for_single_endpoint_case(
            geometry=geometry,
            state=state,
            partition=partition,
            chosen_arc_name=chosen_arc_name,
        )
        yield from _iter_lemma_38_family_recursive(
            geometry=geometry,
            semi_instance=SemiSeparatedInstance(
                state=state,
                partition=next_partition,
                fixed_colors=semi_instance.fixed_colors,
            ),
            stats=stats,
            seen_structures=seen_structures,
        )
        return

    # Lemma 3.8, Step 5.
    x_left, x_right = _split_x_arc(
        geometry=geometry,
        state=state,
        partition=partition,
        chosen_arc_name=chosen_arc_name,
        x=x,
    )
    h_left_mask, h_right_mask = _split_chord_sets(
        geometry=geometry,
        state=state,
        partition=partition,
        chosen_arc_name=chosen_arc_name,
        x_left=x_left,
        x_right=x_right,
    )
    for child_result in iter_lemma_36_family(
        geometry=geometry,
        state=state,
        x_vertices_mask=h_left_mask,
        y_vertices_mask=h_right_mask,
        stats=stats,
    ):
        child_partition = _partition_after_split_branch(
            partition=partition,
            chosen_arc_name=chosen_arc_name,
            x_left=x_left,
            x_right=x_right,
            child_state=child_result.state,
            h_left_mask=h_left_mask,
            h_right_mask=h_right_mask,
        )
        yield from _iter_lemma_38_family_recursive(
            geometry=geometry,
            semi_instance=SemiSeparatedInstance(
                state=child_result.state,
                partition=child_partition,
                fixed_colors=merge_fixed_colors(
                    semi_instance.fixed_colors,
                    child_result.fixed_colors,
                ),
            ),
            stats=stats,
            seen_structures=seen_structures,
        )


def _choose_x_arc(
    *,
    geometry: SosaGeometry,
    state: SosaSearchState,
    partition: CirclePartition,
) -> tuple[str, int]:
    """Return the chosen arc `X` and its endpoint count `x`."""
    top_count = count_active_endpoints_in_arc(
        geometry=geometry,
        state=state,
        partition=partition,
        arc_name="T",
    )
    bottom_count = count_active_endpoints_in_arc(
        geometry=geometry,
        state=state,
        partition=partition,
        arc_name="B",
    )
    if top_count >= bottom_count:
        return "T", top_count
    return "B", bottom_count


def _collapse_empty_top_and_bottom(*, partition: CirclePartition) -> CirclePartition:
    """Return the Step 3 partition where `T` and `B` are empty."""
    return CirclePartition(
        n_endpoints=partition.n_endpoints,
        left_boundary=partition.left_boundary,
        top_boundary=partition.right_boundary,
        right_boundary=partition.right_boundary,
        bottom_boundary=partition.left_boundary,
    )


def _partition_for_single_endpoint_case(
    *,
    geometry: SosaGeometry,
    state: SosaSearchState,
    partition: CirclePartition,
    chosen_arc_name: str,
) -> CirclePartition:
    """Construct `P′` for Lemma 3.8 Step 4."""
    if chosen_arc_name == "T":
        h_lx_mask = chords_between_arcs(
            geometry=geometry,
            state=state,
            first_partition=partition,
            first_arc_name="L",
            second_arc_name="T",
        )
        h_xr_mask = chords_between_arcs(
            geometry=geometry,
            state=state,
            first_partition=partition,
            first_arc_name="T",
            second_arc_name="R",
        )
        if h_lx_mask == 0:
            return CirclePartition(
                n_endpoints=partition.n_endpoints,
                left_boundary=partition.left_boundary,
                top_boundary=partition.top_boundary,
                right_boundary=partition.top_boundary,
                bottom_boundary=partition.bottom_boundary,
            )
        if h_xr_mask == 0:
            return CirclePartition(
                n_endpoints=partition.n_endpoints,
                left_boundary=partition.left_boundary,
                top_boundary=partition.right_boundary,
                right_boundary=partition.right_boundary,
                bottom_boundary=partition.bottom_boundary,
            )
    elif chosen_arc_name == "B":
        h_lx_mask = chords_between_arcs(
            geometry=geometry,
            state=state,
            first_partition=partition,
            first_arc_name="L",
            second_arc_name="B",
        )
        h_xr_mask = chords_between_arcs(
            geometry=geometry,
            state=state,
            first_partition=partition,
            first_arc_name="B",
            second_arc_name="R",
        )
        if h_lx_mask == 0:
            return CirclePartition(
                n_endpoints=partition.n_endpoints,
                left_boundary=partition.left_boundary,
                top_boundary=partition.top_boundary,
                right_boundary=partition.right_boundary,
                bottom_boundary=partition.left_boundary,
            )
        if h_xr_mask == 0:
            return CirclePartition(
                n_endpoints=partition.n_endpoints,
                left_boundary=partition.bottom_boundary,
                top_boundary=partition.top_boundary,
                right_boundary=partition.right_boundary,
                bottom_boundary=partition.bottom_boundary,
            )
    else:
        raise ValueError(f"unknown chosen arc {chosen_arc_name!r}")
    raise AssertionError("Lemma 3.8 Step 4 requires either no L-X chords or no X-R chords")


def _split_x_arc(
    *,
    geometry: SosaGeometry,
    state: SosaSearchState,
    partition: CirclePartition,
    chosen_arc_name: str,
    x: int,
) -> tuple[CirclePartition, CirclePartition]:
    """Split `X` into `X_L` and `X_R` as required by Lemma 3.8 Step 5(a)."""
    if chosen_arc_name == "T":
        x_left_size = (x + 1) // 2
        split_boundary = advance_boundary_inside_arc(
            geometry=geometry,
            state=state,
            partition=partition,
            arc_name="T",
            target_active_endpoints=x_left_size,
        )
        return (
            CirclePartition(
                n_endpoints=partition.n_endpoints,
                left_boundary=partition.top_boundary,
                top_boundary=split_boundary,
                right_boundary=split_boundary,
                bottom_boundary=partition.top_boundary,
            ),
            CirclePartition(
                n_endpoints=partition.n_endpoints,
                left_boundary=split_boundary,
                top_boundary=partition.right_boundary,
                right_boundary=partition.right_boundary,
                bottom_boundary=split_boundary,
            ),
        )
    if chosen_arc_name != "B":
        raise ValueError(f"unknown chosen arc {chosen_arc_name!r}")

    # For B, X_R is the side adjacent to R and X_L is the side adjacent to L.
    x_right_size = x // 2
    split_boundary = advance_boundary_inside_arc(
        geometry=geometry,
        state=state,
        partition=partition,
        arc_name="B",
        target_active_endpoints=x_right_size,
    )
    return (
        CirclePartition(
            n_endpoints=partition.n_endpoints,
            left_boundary=split_boundary,
            top_boundary=partition.left_boundary,
            right_boundary=partition.left_boundary,
            bottom_boundary=split_boundary,
        ),
        CirclePartition(
            n_endpoints=partition.n_endpoints,
            left_boundary=partition.bottom_boundary,
            top_boundary=split_boundary,
            right_boundary=split_boundary,
            bottom_boundary=partition.bottom_boundary,
        ),
    )


def _split_chord_sets(
    *,
    geometry: SosaGeometry,
    state: SosaSearchState,
    partition: CirclePartition,
    chosen_arc_name: str,
    x_left: CirclePartition,
    x_right: CirclePartition,
) -> tuple[int, int]:
    """Return `H_L` and `H_R` from Lemma 3.8 Step 5(a)."""
    if chosen_arc_name not in {"T", "B"}:
        raise ValueError(f"unknown chosen arc {chosen_arc_name!r}")
    return (
        chords_between_partition_arcs(
            geometry=geometry,
            state=state,
            partition=partition,
            left_arc_name="L",
            right_partition=x_right,
            right_arc_name="L",
        ),
        chords_between_partition_arcs(
            geometry=geometry,
            state=state,
            partition=partition,
            left_partition=x_left,
            left_arc_name="L",
            right_arc_name="R",
        ),
    )


def _partition_after_split_branch(
    *,
    partition: CirclePartition,
    chosen_arc_name: str,
    x_left: CirclePartition,
    x_right: CirclePartition,
    child_state: SosaSearchState,
    h_left_mask: int,
    h_right_mask: int,
) -> CirclePartition:
    """Construct `P_{I′}` for Lemma 3.8 Step 5(c)."""
    if child_state.active_vertices_mask & h_left_mask == 0:
        if chosen_arc_name == "T":
            return CirclePartition(
                n_endpoints=partition.n_endpoints,
                left_boundary=partition.left_boundary,
                top_boundary=partition.top_boundary,
                right_boundary=x_right.left_boundary,
                bottom_boundary=partition.bottom_boundary,
            )
        return CirclePartition(
            n_endpoints=partition.n_endpoints,
            left_boundary=partition.left_boundary,
            top_boundary=partition.top_boundary,
            right_boundary=partition.right_boundary,
            bottom_boundary=x_left.left_boundary,
        )
    if child_state.active_vertices_mask & h_right_mask == 0:
        if chosen_arc_name == "T":
            return CirclePartition(
                n_endpoints=partition.n_endpoints,
                left_boundary=partition.left_boundary,
                top_boundary=x_left.top_boundary,
                right_boundary=partition.right_boundary,
                bottom_boundary=partition.bottom_boundary,
            )
        return CirclePartition(
            n_endpoints=partition.n_endpoints,
            left_boundary=x_left.left_boundary,
            top_boundary=partition.top_boundary,
            right_boundary=partition.right_boundary,
            bottom_boundary=partition.bottom_boundary,
        )
    raise AssertionError("Lemma 3.6 output must eliminate either H_L or H_R")
