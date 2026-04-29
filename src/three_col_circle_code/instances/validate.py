from pathlib import Path
from typing import Any, Mapping, Optional, Union

import networkx as nx

from three_col_circle_code.instances.io import load_instance_envelope
from three_col_circle_code.instances.model import (
    InstanceMetadata,
    ValidationReport,
    bucket_for_n,
)


def validate_instance(
    graph: nx.Graph, metadata: Optional[Mapping[str, Any]] = None
) -> ValidationReport:
    """Validate canonical circle-graph structure and optional metadata."""
    report = ValidationReport()

    if graph.is_directed():
        report.add_error("graph.directed", "instance graph must be undirected")
    if graph.is_multigraph():
        report.add_error("graph.multigraph", "instance graph must be simple, not a multigraph")

    _validate_nodes(graph, report)
    _validate_endpoints(graph, report)
    _validate_edges(graph, report)
    _validate_metadata(graph, metadata, report)

    return report


def validate_instance_file(path: Union[str, Path]) -> ValidationReport:
    """Load an instance file and validate its graph and metadata."""
    metadata, graph = load_instance_envelope(path)
    return validate_instance(graph, metadata=metadata)


def _validate_nodes(graph: nx.Graph, report: ValidationReport) -> None:
    for node_id, attrs in graph.nodes(data=True):
        if attrs.get("label") != node_id:
            report.add_error(
                "node.label_mismatch",
                f"node {node_id!r} has label {attrs.get('label')!r}",
            )
        for key in ("l", "r"):
            value = attrs.get(key)
            if not isinstance(value, int):
                report.add_error(
                    "node.endpoint_type",
                    f"node {node_id!r} has non-integer {key}={value!r}",
                )


def _validate_endpoints(graph: nx.Graph, report: ValidationReport) -> None:
    n = graph.number_of_nodes()
    positions = []
    for node_id, attrs in graph.nodes(data=True):
        left = attrs.get("l")
        right = attrs.get("r")
        if not isinstance(left, int) or not isinstance(right, int):
            continue
        if not (0 <= left < right < 2 * n):
            report.add_error(
                "node.endpoint_order",
                f"node {node_id!r} has invalid endpoints ({left}, {right}) for n={n}",
            )
        positions.extend((left, right))

    if len(positions) != 2 * n:
        report.add_error(
            "graph.endpoint_count",
            f"graph has {len(positions)} endpoint positions but expected {2 * n}",
        )
        return

    expected = set(range(2 * n))
    actual = set(positions)
    if len(actual) != len(positions):
        report.add_error("graph.endpoint_duplicate", "endpoint positions must be unique")
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        report.add_error(
            "graph.endpoint_coverage",
            f"endpoint positions must be exactly 0..{2 * n - 1}; missing={missing}, extra={extra}",
        )


def _validate_edges(graph: nx.Graph, report: ValidationReport) -> None:
    node_data = tuple(graph.nodes(data=True))
    node_ids = tuple(node_id for node_id, _attrs in node_data)
    node_order = {node_id: index for index, node_id in enumerate(node_ids)}
    endpoints = tuple(
        (
            attrs.get("l") if isinstance(attrs.get("l"), int) else None,
            attrs.get("r") if isinstance(attrs.get("r"), int) else None,
        )
        for _node_id, attrs in node_data
    )
    adjacency_sets = [set() for _node_id in node_ids]
    extra: list[tuple[Any, Any]] = []
    for u, v in graph.edges():
        u_index = node_order.get(u)
        v_index = node_order.get(v)
        if u_index is None or v_index is None:
            extra.append(_canonical_edge(u, v))
            continue
        adjacency_sets[u_index].add(v_index)
        adjacency_sets[v_index].add(u_index)

    missing: list[tuple[Any, Any]] = []
    for left_index, left_node in enumerate(node_ids):
        left_l, left_r = endpoints[left_index]
        if left_l is None or left_r is None:
            continue
        left_neighbors = adjacency_sets[left_index]
        for right_index in range(left_index + 1, len(node_ids)):
            right_l, right_r = endpoints[right_index]
            if right_l is None or right_r is None:
                continue
            has_edge = right_index in left_neighbors
            crosses = (left_l < right_l < left_r < right_r) or (
                right_l < left_l < right_r < left_r
            )
            if crosses and not has_edge:
                missing.append(_canonical_edge(left_node, node_ids[right_index]))
            elif has_edge and not crosses:
                extra.append(_canonical_edge(left_node, node_ids[right_index]))

    if missing or extra:
        report.add_error(
            "graph.edge_mismatch",
            f"edge set does not match chord crossings; missing={missing}, extra={extra}",
        )


def _validate_metadata(
    graph: nx.Graph, metadata: Optional[Mapping[str, Any]], report: ValidationReport
) -> None:
    if metadata is None:
        return
    metadata_obj = InstanceMetadata.from_mapping(metadata)
    if metadata_obj.n != graph.number_of_nodes():
        report.add_error(
            "metadata.n_mismatch",
            f"metadata n={metadata_obj.n} does not match graph node count {graph.number_of_nodes()}",
        )
    if metadata_obj.m != graph.number_of_edges():
        report.add_error(
            "metadata.m_mismatch",
            f"metadata m={metadata_obj.m} does not match graph edge count {graph.number_of_edges()}",
        )
    expected_bucket = bucket_for_n(graph.number_of_nodes())
    if metadata_obj.bucket != expected_bucket:
        report.add_error(
            "metadata.bucket_mismatch",
            f"metadata bucket={metadata_obj.bucket!r} does not match expected {expected_bucket!r}",
        )


def _cross(attrs_a: Mapping[str, Any], attrs_b: Mapping[str, Any]) -> bool:
    a_l = attrs_a.get("l")
    a_r = attrs_a.get("r")
    b_l = attrs_b.get("l")
    b_r = attrs_b.get("r")
    if not all(isinstance(value, int) for value in (a_l, a_r, b_l, b_r)):
        return False
    return (a_l < b_l < a_r < b_r) or (b_l < a_l < b_r < a_r)


def _canonical_edge(u: Any, v: Any) -> tuple[Any, Any]:
    return (u, v) if u <= v else (v, u)
