from dataclasses import dataclass
from typing import Any

import networkx as nx


@dataclass(frozen=True, slots=True)
class SosaGeometry:
    """Immutable geometry and adjacency view derived from a canonical circle graph."""

    node_ids: tuple[Any, ...]
    node_to_index: dict[Any, int]
    left_endpoints: tuple[int, ...]
    right_endpoints: tuple[int, ...]
    endpoint_owner: tuple[int, ...]
    adjacency_masks: tuple[int, ...]
    neighbor_indices: tuple[tuple[int, ...], ...]

    @classmethod
    def from_graph(cls, graph: nx.Graph) -> "SosaGeometry":
        """Construct immutable geometry from a validated chord-annotated graph."""
        node_ids = tuple(graph.nodes())
        node_to_index = {node_id: index for index, node_id in enumerate(node_ids)}
        n_vertices = len(node_ids)

        left_endpoints = [0] * n_vertices
        right_endpoints = [0] * n_vertices
        endpoint_owner = [-1] * (2 * n_vertices)
        adjacency_masks = [0] * n_vertices
        neighbor_indices = [[] for _ in range(n_vertices)]

        for index, node_id in enumerate(node_ids):
            attrs = graph.nodes[node_id]
            left = int(attrs["l"])
            right = int(attrs["r"])
            left_endpoints[index] = left
            right_endpoints[index] = right
            endpoint_owner[left] = index
            endpoint_owner[right] = index

        for left_node, right_node in graph.edges():
            left_index = node_to_index[left_node]
            right_index = node_to_index[right_node]
            adjacency_masks[left_index] |= 1 << right_index
            adjacency_masks[right_index] |= 1 << left_index
            neighbor_indices[left_index].append(right_index)
            neighbor_indices[right_index].append(left_index)

        return cls(
            node_ids=node_ids,
            node_to_index=node_to_index,
            left_endpoints=tuple(left_endpoints),
            right_endpoints=tuple(right_endpoints),
            endpoint_owner=tuple(endpoint_owner),
            adjacency_masks=tuple(adjacency_masks),
            neighbor_indices=tuple(tuple(indices) for indices in neighbor_indices),
        )

    @property
    def n_vertices(self) -> int:
        """Return the number of vertices/chords in the instance."""
        return len(self.node_ids)

    @property
    def m_edges(self) -> int:
        """Return the number of graph edges implied by the geometry."""
        return sum(len(indices) for indices in self.neighbor_indices) // 2
