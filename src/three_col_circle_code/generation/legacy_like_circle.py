import random

from three_col_circle_code.generation.circle_state import (
    IncrementalCircleState,
    build_graph_from_state,
)
from three_col_circle_code.generation.color_utils import available_colors, validate_num_colors


def generate_random_circle_graph_fast(size, *, rng=None, max_attempts_per_node=None):
    """Generate a connected K4-free circle graph using the legacy insertion model."""
    state = _generate_incremental_circle_state(
        size,
        rng=rng,
        max_attempts_per_node=max_attempts_per_node,
    )
    return build_graph_from_state(state)


def generate_random_circle_graph_yes_fast(size, *, rng=None, max_attempts_per_node=None, num_colors=3):
    """Generate a connected K4-free k-colorable circle graph using the legacy insertion model."""
    validate_num_colors(num_colors)
    state = _generate_incremental_circle_state(
        size,
        rng=rng,
        max_attempts_per_node=max_attempts_per_node,
        color_selector=lambda neighbors, colors: _choose_compatible_color(
            neighbors,
            colors,
            num_colors,
        ),
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

            _commit_candidate(
                state,
                node_id,
                first_position,
                second_position,
                neighbors,
                color=color,
            )
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


def _insert_node_at_positions(endpoint_order, node_id, first_position, second_position):
    endpoint_order.insert(first_position, node_id)
    endpoint_order.insert(second_position, node_id)


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
    if len(neighbors) < 3:
        return False
    neighbor_list = tuple(neighbors)
    for index, left in enumerate(neighbor_list):
        left_neighbors = adjacency[left]
        for right in neighbor_list[index + 1 :]:
            if right not in left_neighbors:
                continue
            if left_neighbors.intersection(adjacency[right], neighbors):
                return True
    return False


def _commit_candidate(state, node_id, first_position, second_position, neighbors, *, color=None):
    _insert_node_at_positions(state.endpoint_order, node_id, first_position, second_position)
    state.adjacency[node_id] = set(neighbors)
    for neighbor in neighbors:
        state.adjacency[neighbor].add(node_id)
    if state.colors is not None and color is not None:
        state.colors[node_id] = color


def _choose_compatible_color(neighbors, colors, num_colors):
    remaining_colors = available_colors(colors, neighbors, num_colors)
    if remaining_colors:
        return remaining_colors[0]
    return None
