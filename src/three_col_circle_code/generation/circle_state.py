from dataclasses import dataclass, field

import networkx as nx


@dataclass
class IncrementalCircleState:
    endpoint_order: list[int] = field(default_factory=list)
    adjacency: dict[int, set[int]] = field(default_factory=dict)
    colors: dict[int, int] | None = None


def build_graph_from_state(state: IncrementalCircleState) -> nx.Graph:
    graph = nx.Graph()
    endpoints: dict[int, list[int]] = {}
    for position, node_id in enumerate(state.endpoint_order):
        if node_id in endpoints:
            endpoints[node_id][1] = position
        else:
            endpoints[node_id] = [position, position]
    for node_id in range(len(state.adjacency)):
        left, right = endpoints[node_id]
        node_attrs = {
            "label": node_id,
            "l": left,
            "r": right,
        }
        if state.colors is not None and node_id in state.colors:
            node_attrs["color"] = state.colors[node_id]
        graph.add_node(node_id, **node_attrs)
    for node_id, neighbors in state.adjacency.items():
        for neighbor in neighbors:
            if node_id < neighbor:
                graph.add_edge(node_id, neighbor)
    return graph


def find_endpoints(endpoint_order: list[int], node_id: int) -> tuple[int, int]:
    left = endpoint_order.index(node_id)
    right = len(endpoint_order) - 1 - endpoint_order[::-1].index(node_id)
    return left, right
