import argparse
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Optional, Union

import networkx as nx

from three_col_circle_code.instances.catalog import discover_instances
from three_col_circle_code.instances.io import load_instance
from three_col_circle_code.instances.model import (
    InstanceFormatError,
    InstanceMetadata,
    InstanceRecord,
    bucket_for_n,
)
from three_col_circle_code.instances.validate import validate_instance


DEFAULT_ORDER_WRAP = 64
_CIRCLE_PREFIX = ("ircle", "representation")
_METADATA_NONE = "none"


def write_dimacs_circle(
    record: InstanceRecord,
    path: Union[str, Path],
    *,
    wrap: int = DEFAULT_ORDER_WRAP,
) -> Path:
    """Write one instance as DIMACS edge format with circle-order comments."""
    if wrap < 1:
        raise ValueError("wrap must be at least 1")

    graph = record.graph
    report = validate_instance(graph)
    if not report.ok:
        errors = [{"code": issue.code, "message": issue.message} for issue in report.errors]
        raise InstanceFormatError(f"cannot export invalid circle instance: {errors}")

    node_ids = _sorted_nodes(graph)
    node_to_dimacs = {node_id: index + 1 for index, node_id in enumerate(node_ids)}
    order = _circle_order_from_graph(graph, node_to_dimacs)
    edges = sorted(
        (min(node_to_dimacs[u], node_to_dimacs[v]), max(node_to_dimacs[u], node_to_dimacs[v]))
        for u, v in graph.edges()
    )

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as outfile:
        _write_metadata_comments(outfile, record.metadata)
        outfile.write("c ircle representation START\n")
        for index in range(0, len(order), wrap):
            chunk = " ".join(str(vertex_id) for vertex_id in order[index : index + wrap])
            outfile.write(f"c {chunk}\n")
        outfile.write("c ircle representation END\n")
        outfile.write(f"p edge {len(node_ids)} {len(edges)}\n")
        for u, v in edges:
            outfile.write(f"e {u} {v}\n")
    return output_path


def read_dimacs_circle(path: Union[str, Path]) -> InstanceRecord:
    """Read a DIMACS circle instance and validate graph/circle consistency."""
    input_path = Path(path)
    n_vertices, declared_edges, edges, order = _parse_dimacs_circle(input_path)
    if order is None:
        raise InstanceFormatError("DIMACS file is missing a circle representation block")

    graph = _graph_from_dimacs_circle(n_vertices, edges, order)
    metadata = InstanceMetadata(
        instance_id=input_path.stem,
        family="dimacs-circle",
        seed=None,
        generator="dimacs_circle_import",
        n=graph.number_of_nodes(),
        m=graph.number_of_edges(),
        bucket=bucket_for_n(graph.number_of_nodes()),
        source="imported",
        created_at=datetime.now(UTC).isoformat(),
    )
    if declared_edges != graph.number_of_edges():
        raise InstanceFormatError(
            f"problem line declares {declared_edges} edge(s), but {graph.number_of_edges()} were read"
        )
    report = validate_instance(graph, metadata=metadata.to_dict())
    if not report.ok:
        errors = [{"code": issue.code, "message": issue.message} for issue in report.errors]
        raise InstanceFormatError(f"DIMACS circle instance did not validate: {errors}")
    return InstanceRecord(metadata=metadata, graph=graph)


def export_dimacs_circle_tree(
    input_root: Union[str, Path],
    output_root: Union[str, Path],
    *,
    wrap: int = DEFAULT_ORDER_WRAP,
) -> list[Path]:
    """Export all JSON instances below a root to matching `.col` files."""
    input_root_path = Path(input_root)
    output_root_path = Path(output_root)
    output_paths: list[Path] = []
    for input_path in discover_instances(input_root_path):
        record = load_instance(input_path)
        relative = input_path.relative_to(input_root_path) if input_root_path.is_dir() else input_path.name
        output_path = output_root_path / Path(relative).with_suffix(".col")
        output_paths.append(write_dimacs_circle(record, output_path, wrap=wrap))
    return output_paths


def export_dimacs_circle_in_place(
    input_root: Union[str, Path],
    *,
    wrap: int = DEFAULT_ORDER_WRAP,
) -> list[Path]:
    """Export JSON instances as sibling `.col` files."""
    output_paths: list[Path] = []
    for input_path in discover_instances(input_root):
        record = load_instance(input_path)
        output_paths.append(write_dimacs_circle(record, input_path.with_suffix(".col"), wrap=wrap))
    return output_paths


def main(argv: Optional[Iterable[str]] = None) -> int:
    """Export canonical JSON instances to DIMACS circle files."""
    parser = argparse.ArgumentParser(description="Export JSON circle instances as DIMACS edge files.")
    parser.add_argument("--input", required=True, type=Path, help="JSON instance file or directory")
    parser.add_argument(
        "--output",
        type=Path,
        help="Output .col file or directory. Omit to write .col files next to input JSON files.",
    )
    parser.add_argument("--wrap", type=int, default=DEFAULT_ORDER_WRAP)
    args = parser.parse_args(list(argv) if argv is not None else None)

    input_path = args.input
    if args.output is None:
        for output_path in export_dimacs_circle_in_place(input_path, wrap=args.wrap):
            print(output_path)
        return 0

    if input_path.is_file():
        record = load_instance(input_path)
        output_path = args.output
        if output_path.suffix == "":
            output_path = output_path / input_path.with_suffix(".col").name
        print(write_dimacs_circle(record, output_path, wrap=args.wrap))
        return 0

    for output_path in export_dimacs_circle_tree(input_path, args.output, wrap=args.wrap):
        print(output_path)
    return 0


def _parse_dimacs_circle(path: Path) -> tuple[int, int, list[tuple[int, int]], Optional[list[int]]]:
    n_vertices: Optional[int] = None
    declared_edges: Optional[int] = None
    edges: list[tuple[int, int]] = []
    order: list[int] = []
    in_circle_block = False
    saw_circle_block = False

    with path.open(encoding="utf-8") as infile:
        for line_number, raw_line in enumerate(infile, start=1):
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split()
            tag = parts[0]
            if tag == "c":
                action = _circle_comment_action(parts[1:])
                if action == "START":
                    if in_circle_block:
                        raise InstanceFormatError(f"nested circle representation block at line {line_number}")
                    if saw_circle_block:
                        raise InstanceFormatError(f"duplicate circle representation block at line {line_number}")
                    in_circle_block = True
                    saw_circle_block = True
                elif action == "END":
                    if not in_circle_block:
                        raise InstanceFormatError(f"circle representation END without START at line {line_number}")
                    in_circle_block = False
                elif in_circle_block:
                    if action is not None:
                        raise InstanceFormatError(
                            f"unsupported circle representation directive at line {line_number}: {line}"
                        )
                    order.extend(_parse_ints(parts[1:], line_number=line_number))
                continue
            if tag == "p":
                if len(parts) != 4 or parts[1] not in {"edge", "col"}:
                    raise InstanceFormatError(f"unsupported DIMACS problem line at line {line_number}: {line}")
                if n_vertices is not None:
                    raise InstanceFormatError(f"duplicate DIMACS problem line at line {line_number}")
                n_vertices = _parse_positive_int(parts[2], line_number=line_number)
                declared_edges = _parse_nonnegative_int(parts[3], line_number=line_number)
                continue
            if tag == "e":
                if len(parts) != 3:
                    raise InstanceFormatError(f"malformed edge line at line {line_number}: {line}")
                edges.append(
                    (
                        _parse_positive_int(parts[1], line_number=line_number),
                        _parse_positive_int(parts[2], line_number=line_number),
                    )
                )
                continue
            raise InstanceFormatError(f"unsupported DIMACS line at {line_number}: {line}")

    if in_circle_block:
        raise InstanceFormatError("circle representation block is missing END")
    if n_vertices is None or declared_edges is None:
        raise InstanceFormatError("DIMACS file is missing a problem line")
    return n_vertices, declared_edges, edges, order if saw_circle_block else None


def _circle_comment_action(parts: list[str]) -> Optional[str]:
    if len(parts) != 3:
        return None
    if tuple(parts[:2]) != _CIRCLE_PREFIX:
        return None
    return parts[2]


def _write_metadata_comments(outfile: object, metadata: InstanceMetadata) -> None:
    outfile.write(f"c instance id {metadata.instance_id}\n")
    outfile.write(f"c family {metadata.family}\n")
    outfile.write(f"c seed {_format_optional_value(metadata.seed)}\n")
    outfile.write(f"c n {metadata.n}\n")
    outfile.write(f"c m {metadata.m}\n")
    outfile.write(f"c average degree {_format_float(_average_degree(metadata.n, metadata.m))}\n")
    outfile.write(f"c num colors {metadata.num_colors}\n")
    outfile.write(f"c source {metadata.source}\n")
    outfile.write(f"c generator {metadata.generator}\n")
    outfile.write(f"c created at {metadata.created_at}\n")
    outfile.write(
        f"c generation time seconds {_format_optional_value(metadata.generation_time_seconds)}\n"
    )
    outfile.write(
        f"c max attempts per node {_format_optional_value(metadata.max_attempts_per_node)}\n"
    )


def _format_optional_value(value: object) -> str:
    return _METADATA_NONE if value is None else str(value)


def _average_degree(n_vertices: int, n_edges: int) -> float:
    if n_vertices == 0:
        return 0.0
    return 2.0 * n_edges / n_vertices


def _format_float(value: float) -> str:
    return format(value, ".12g")


def _graph_from_dimacs_circle(
    n_vertices: int,
    edges: list[tuple[int, int]],
    order: list[int],
) -> nx.Graph:
    _validate_circle_order(order, n_vertices)
    graph = nx.Graph()
    endpoint_positions: dict[int, list[int]] = {vertex_id: [] for vertex_id in range(1, n_vertices + 1)}
    for position, vertex_id in enumerate(order):
        endpoint_positions[vertex_id].append(position)
    for vertex_id in range(1, n_vertices + 1):
        left, right = sorted(endpoint_positions[vertex_id])
        graph.add_node(vertex_id, label=vertex_id, l=left, r=right)
    for u, v in edges:
        if not (1 <= u <= n_vertices and 1 <= v <= n_vertices):
            raise InstanceFormatError(f"edge ({u}, {v}) uses vertex outside 1..{n_vertices}")
        if u == v:
            raise InstanceFormatError(f"self-loop ({u}, {v}) is not supported")
        graph.add_edge(u, v)
    return graph


def _validate_circle_order(order: list[int], n_vertices: int) -> None:
    expected_length = 2 * n_vertices
    if len(order) != expected_length:
        raise InstanceFormatError(
            f"circle order has {len(order)} endpoint(s), expected {expected_length}"
        )
    counts = Counter(order)
    expected_vertices = set(range(1, n_vertices + 1))
    actual_vertices = set(counts)
    if actual_vertices != expected_vertices:
        missing = sorted(expected_vertices - actual_vertices)
        extra = sorted(actual_vertices - expected_vertices)
        raise InstanceFormatError(
            f"circle order must use exactly vertex ids 1..{n_vertices}; missing={missing}, extra={extra}"
        )
    bad_counts = {vertex_id: count for vertex_id, count in counts.items() if count != 2}
    if bad_counts:
        raise InstanceFormatError(f"each vertex id must appear exactly twice; counts={bad_counts}")


def _circle_order_from_graph(graph: nx.Graph, node_to_dimacs: dict[object, int]) -> list[int]:
    n_vertices = graph.number_of_nodes()
    order: list[Optional[int]] = [None] * (2 * n_vertices)
    for node_id, dimacs_id in node_to_dimacs.items():
        attrs = graph.nodes[node_id]
        for key in ("l", "r"):
            position = attrs.get(key)
            if not isinstance(position, int) or not (0 <= position < 2 * n_vertices):
                raise InstanceFormatError(
                    f"node {node_id!r} has invalid endpoint {key}={position!r}"
                )
            if order[position] is not None:
                raise InstanceFormatError(f"duplicate endpoint position {position}")
            order[position] = dimacs_id
    if any(vertex_id is None for vertex_id in order):
        missing = [index for index, vertex_id in enumerate(order) if vertex_id is None]
        raise InstanceFormatError(f"missing endpoint position(s): {missing}")
    return [vertex_id for vertex_id in order if vertex_id is not None]


def _sorted_nodes(graph: nx.Graph) -> list[object]:
    try:
        return sorted(graph.nodes())
    except TypeError:
        return sorted(graph.nodes(), key=repr)


def _parse_ints(values: list[str], *, line_number: int) -> list[int]:
    return [_parse_positive_int(value, line_number=line_number) for value in values]


def _parse_positive_int(value: str, *, line_number: int) -> int:
    parsed = _parse_nonnegative_int(value, line_number=line_number)
    if parsed < 1:
        raise InstanceFormatError(f"expected positive integer at line {line_number}: {value!r}")
    return parsed


def _parse_nonnegative_int(value: str, *, line_number: int) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise InstanceFormatError(f"expected integer at line {line_number}: {value!r}") from exc
    if parsed < 0:
        raise InstanceFormatError(f"expected nonnegative integer at line {line_number}: {value!r}")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
