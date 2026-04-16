import random

from three_col_circle_code.generation.circle_state import (
    IncrementalCircleState,
    build_graph_from_state,
)


def generate_random_circle_graph_fast(size, *, rng=None, max_attempts_per_node=None):
    """Generate a connected K4-free circle graph using the legacy insertion model."""
    state = _generate_incremental_circle_state(
        size,
        rng=rng,
        max_attempts_per_node=max_attempts_per_node,
    )
    return build_graph_from_state(state)


def generate_random_circle_graph_yes_fast(size, *, rng=None, max_attempts_per_node=None):
    """Generate a connected K4-free 3-colorable circle graph using the legacy insertion model."""
    state = _generate_incremental_circle_state(
        size,
        rng=rng,
        max_attempts_per_node=max_attempts_per_node,
        color_selector=_choose_legacy_compatible_color,
    )
    return build_graph_from_state(state)


def _generate_incremental_circle_state(
    size,
    *,
    rng=None,
    max_attempts_per_node=None,
    color_selector=None,
):
    _validate_generation_request(size, max_attempts_per_node)

    rng = rng or random
    state = IncrementalCircleState(colors={} if color_selector is not None else None)

    for node_id in range(size):
        searching = True
        attempts = 0
        while searching:
            if max_attempts_per_node is not None and attempts >= max_attempts_per_node:
                break
            first_position, second_position = _sample_insert_positions(len(state.endpoint_order), rng=rng)
            left, right = _candidate_neighbor_slice(first_position, second_position)
            neighbors = _candidate_neighbors_between(state.endpoint_order, left, right)
            if not _candidate_is_connected(node_id, neighbors):
                attempts += 1
                continue
            if _contains_triangle(neighbors, state.adjacency):
                attempts += 1
                continue

            color = None
            if color_selector is not None:
                color = color_selector(neighbors, state.colors)
                if color is None:
                    attempts += 1
                    continue

            candidate_order = _build_candidate_order(
                state.endpoint_order,
                node_id,
                first_position,
                second_position,
            )
            _commit_candidate(state, node_id, candidate_order, neighbors, color=color)
            searching = False
            attempts += 1
        if searching:
            raise RuntimeError("failed to generate fast random circle graph for node " + str(node_id))

    return state


def _validate_generation_request(size, max_attempts_per_node):
    if size < 0:
        raise ValueError("size must be non-negative")
    if max_attempts_per_node is not None and max_attempts_per_node < 1:
        raise ValueError("max_attempts_per_node must be at least 1")


def _build_candidate_order(endpoint_order, node_id, first_position, second_position):
    candidate_order = endpoint_order.copy()
    candidate_order.insert(first_position, node_id)
    candidate_order.insert(second_position, node_id)
    return candidate_order


def _sample_insert_positions(endpoint_order_len, *, rng):
    return (
        rng.randint(0, endpoint_order_len),
        rng.randint(0, endpoint_order_len + 1),
    )


def _candidate_neighbor_slice(first_position, second_position):
    if second_position <= first_position:
        return second_position, first_position
    return first_position, second_position - 1


def _candidate_neighbors_between(endpoint_order, left, right):
    neighbors: set[int] = set()
    for index in range(left, right):
        value = endpoint_order[index]
        if value in neighbors:
            neighbors.remove(value)
        else:
            neighbors.add(value)
    return neighbors


def _candidate_is_connected(node_id, neighbors):
    return node_id == 0 or bool(neighbors)


def _contains_triangle(neighbors, adjacency):
    neighbor_list = tuple(neighbors)
    for index, left in enumerate(neighbor_list):
        left_neighbors = adjacency[left]
        for right in neighbor_list[index + 1 :]:
            if right not in left_neighbors:
                continue
            if left_neighbors.intersection(adjacency[right], neighbors):
                return True
    return False


def _commit_candidate(state, node_id, candidate_order, neighbors, *, color=None):
    state.endpoint_order = candidate_order
    state.adjacency[node_id] = set(neighbors)
    for neighbor in neighbors:
        state.adjacency[neighbor].add(node_id)
    if state.colors is not None and color is not None:
        state.colors[node_id] = color


def _choose_legacy_compatible_color(neighbors, colors):
    used_colors = {colors[neighbor] for neighbor in neighbors}
    remaining_colors = {1, 2, 3} - used_colors
    if remaining_colors:
        return remaining_colors.pop()
    return None
