import sys
import random
from pathlib import Path

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.solvers.sosa.colors import ALL_COLOR_MASK, COLOR_MASK_ORDER
from three_col_circle_code.solvers.sosa.geometry import SosaGeometry
from three_col_circle_code.solvers.sosa.mask_ops import iter_mask_indices
from three_col_circle_code.solvers.sosa.types import SosaSearchState


def graph_from_endpoints(endpoint_pairs: tuple[tuple[int, int], ...]) -> nx.Graph:
    graph = nx.Graph()
    for node_id, (left, right) in enumerate(endpoint_pairs):
        graph.add_node(node_id, label=node_id, l=left, r=right)
    for left_node, (a_l, a_r) in enumerate(endpoint_pairs):
        for right_node, (b_l, b_r) in enumerate(endpoint_pairs):
            if left_node >= right_node:
                continue
            if (a_l < b_l < a_r < b_r) or (b_l < a_l < b_r < a_r):
                graph.add_edge(left_node, right_node)
    return graph


def geometry_from_endpoints(endpoint_pairs: tuple[tuple[int, int], ...]) -> SosaGeometry:
    return SosaGeometry.from_graph(graph_from_endpoints(endpoint_pairs))


def state_from_allowed_masks(*allowed_masks: int) -> SosaSearchState:
    return SosaSearchState(
        active_vertices_mask=(1 << len(allowed_masks)) - 1,
        allowed_color_masks=tuple(allowed_masks),
    )


def vertex_mask(*vertex_indices: int) -> int:
    mask = 0
    for vertex_index in vertex_indices:
        mask |= 1 << vertex_index
    return mask


def solve_state_bruteforce(geometry: SosaGeometry, state: SosaSearchState) -> bool:
    active_indices = tuple(iter_mask_indices(state.active_vertices_mask))
    if any(state.allowed_color_masks[vertex_index] == 0 for vertex_index in active_indices):
        return False

    order = sorted(
        active_indices,
        key=lambda vertex_index: sum(
            1
            for neighbor_index in geometry.neighbor_indices[vertex_index]
            if state.is_active(neighbor_index)
        ),
        reverse=True,
    )
    chosen_masks: dict[int, int] = {}

    def backtrack(position: int) -> bool:
        if position == len(order):
            return True
        vertex_index = order[position]
        allowed_mask = state.allowed_color_masks[vertex_index]
        used_mask = 0
        for neighbor_index in geometry.neighbor_indices[vertex_index]:
            used_mask |= chosen_masks.get(neighbor_index, 0)
        available_mask = allowed_mask & (ALL_COLOR_MASK ^ used_mask)
        for color_mask in COLOR_MASK_ORDER:
            if not (available_mask & color_mask):
                continue
            chosen_masks[vertex_index] = color_mask
            if backtrack(position + 1):
                return True
            del chosen_masks[vertex_index]
        return False

    return backtrack(0)


def is_valid_coloring_by_node(graph: nx.Graph, coloring_by_node: dict[int, str]) -> bool:
    """Return whether the node-id coloring is a proper 3-coloring of the graph."""
    allowed_colors = {"red", "green", "blue"}
    if set(coloring_by_node) != set(graph.nodes()):
        return False
    if any(color_name not in allowed_colors for color_name in coloring_by_node.values()):
        return False
    return all(
        coloring_by_node[left_node] != coloring_by_node[right_node]
        for left_node, right_node in graph.edges()
    )


def enumerate_endpoint_pairings(n_vertices: int) -> tuple[tuple[tuple[int, int], ...], ...]:
    """Enumerate all perfect matchings on endpoint positions `0..2n-1`."""
    if n_vertices < 0:
        raise ValueError("n_vertices must be non-negative")
    endpoints = tuple(range(2 * n_vertices))
    return tuple(_enumerate_pairings_recursive(endpoints))


def random_endpoint_pairing(n_vertices: int, *, seed: int) -> tuple[tuple[int, int], ...]:
    """Return one seeded random perfect matching on endpoint positions `0..2n-1`."""
    if n_vertices < 0:
        raise ValueError("n_vertices must be non-negative")
    rng = random.Random(seed)
    endpoints = list(range(2 * n_vertices))
    rng.shuffle(endpoints)
    pairs = []
    for index in range(0, len(endpoints), 2):
        left = min(endpoints[index], endpoints[index + 1])
        right = max(endpoints[index], endpoints[index + 1])
        pairs.append((left, right))
    return tuple(sorted(pairs))


def _enumerate_pairings_recursive(
    endpoints: tuple[int, ...],
) -> tuple[tuple[tuple[int, int], ...], ...]:
    if not endpoints:
        return ((),)

    first = endpoints[0]
    pairings = []
    for partner_index in range(1, len(endpoints)):
        partner = endpoints[partner_index]
        remaining = endpoints[1:partner_index] + endpoints[partner_index + 1 :]
        for suffix in _enumerate_pairings_recursive(remaining):
            pairings.append(((first, partner),) + suffix)
    return tuple(pairings)
