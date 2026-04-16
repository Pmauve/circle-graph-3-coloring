from three_col_circle_code.solvers.sosa.geometry import SosaGeometry
from three_col_circle_code.solvers.sosa.mask_ops import iter_mask_indices
from three_col_circle_code.solvers.sosa.partition import CirclePartition
from three_col_circle_code.solvers.sosa.types import SosaSearchState


def count_active_endpoints_in_arc(
    *,
    geometry: SosaGeometry,
    state: SosaSearchState,
    partition: CirclePartition,
    arc_name: str,
) -> int:
    """Count the active endpoints contained in one named arc of P."""
    count = 0
    for position in partition.arc_positions(arc_name):
        owner_index = geometry.endpoint_owner[position]
        if owner_index != -1 and state.is_active(owner_index):
            count += 1
    return count


def chords_between_arcs(
    *,
    geometry: SosaGeometry,
    state: SosaSearchState,
    first_partition: CirclePartition,
    first_arc_name: str,
    second_arc_name: str,
    second_partition: CirclePartition | None = None,
) -> int:
    """Return active chords whose endpoints lie in two named arcs."""
    second_partition = second_partition or first_partition
    vertices_mask = 0
    for vertex_index in iter_mask_indices(state.active_vertices_mask):
        left_endpoint = geometry.left_endpoints[vertex_index]
        right_endpoint = geometry.right_endpoints[vertex_index]
        if (
            first_partition.contains_position(first_arc_name, left_endpoint)
            and second_partition.contains_position(second_arc_name, right_endpoint)
        ) or (
            first_partition.contains_position(first_arc_name, right_endpoint)
            and second_partition.contains_position(second_arc_name, left_endpoint)
        ):
            vertices_mask |= 1 << vertex_index
    return vertices_mask


def chords_between_partition_arcs(
    *,
    geometry: SosaGeometry,
    state: SosaSearchState,
    partition: CirclePartition,
    left_arc_name: str,
    right_arc_name: str,
    left_partition: CirclePartition | None = None,
    right_partition: CirclePartition | None = None,
) -> int:
    """Return active chords with one endpoint in each of two possibly different arc views."""
    return chords_between_arcs(
        geometry=geometry,
        state=state,
        first_partition=left_partition or partition,
        first_arc_name=left_arc_name,
        second_partition=right_partition or partition,
        second_arc_name=right_arc_name,
    )


def restrict_state_to_arc(
    *,
    geometry: SosaGeometry,
    state: SosaSearchState,
    partition: CirclePartition,
    arc_name: str,
) -> SosaSearchState:
    """Return the subinstance I_A(P) obtained by keeping only one arc's internal chords."""
    active_vertices_mask = 0
    for vertex_index in iter_mask_indices(state.active_vertices_mask):
        if (
            partition.endpoint_arc(geometry.left_endpoints[vertex_index]) == arc_name
            and partition.endpoint_arc(geometry.right_endpoints[vertex_index]) == arc_name
        ):
            active_vertices_mask |= 1 << vertex_index
    return SosaSearchState(
        active_vertices_mask=active_vertices_mask,
        allowed_color_masks=state.allowed_color_masks,
    )


def advance_boundary_inside_arc(
    *,
    geometry: SosaGeometry,
    state: SosaSearchState,
    partition: CirclePartition,
    arc_name: str,
    target_active_endpoints: int,
) -> int:
    """Advance a split boundary inside T or B by a number of active endpoints."""
    normalized_arc_name = arc_name.upper()
    if target_active_endpoints == 0:
        if normalized_arc_name == "T":
            return partition.top_boundary
        if normalized_arc_name == "B":
            return partition.bottom_boundary
        raise ValueError("Lemma 3.8 only splits T or B")

    remaining = target_active_endpoints
    for position in partition.arc_positions(normalized_arc_name):
        owner_index = geometry.endpoint_owner[position]
        if owner_index == -1 or not state.is_active(owner_index):
            continue
        remaining -= 1
        if remaining == 0:
            return (position + 1) % partition.n_endpoints
    raise AssertionError("failed to split the chosen arc in Lemma 3.8")
