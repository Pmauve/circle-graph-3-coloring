import json
from datetime import UTC, datetime
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple, Union

import networkx as nx
from networkx.readwrite import json_graph

from three_col_circle_code.generation.families import infer_legacy_family_from_parts
from three_col_circle_code.instances.model import (
    CANONICAL_NODE_LINK_EDGES_KEY,
    INSTANCE_FORMAT_VERSION,
    LEGACY_NODE_LINK_EDGES_KEY,
    InstanceFormatError,
    InstanceMetadata,
    InstanceRecord,
    build_legacy_metadata,
)


def load_instance(path: Union[str, Path], *, validate: bool = True) -> InstanceRecord:
    """Load a canonical or legacy instance file into an InstanceRecord."""
    instance_path = Path(path)
    if instance_path.suffix == ".col":
        from three_col_circle_code.instances.dimacs_circle import (
            read_dimacs_circle,
            read_dimacs_circle_unvalidated,
        )

        if validate:
            return read_dimacs_circle(instance_path)
        return read_dimacs_circle_unvalidated(instance_path)
    metadata, graph = load_instance_envelope(path)
    return InstanceRecord(metadata=InstanceMetadata.from_mapping(metadata), graph=graph)


def load_instance_envelope(
    path: Union[str, Path],
    *,
    validate: bool = True,
) -> Tuple[Dict[str, Any], nx.Graph]:
    """Load an instance file and return metadata and graph separately."""
    instance_path = Path(path)
    if instance_path.suffix == ".col":
        record = load_instance(instance_path, validate=validate)
        return deepcopy(record.metadata.to_dict()), record.graph
    with instance_path.open(encoding="utf-8") as infile:
        payload = json.load(infile)

    if not isinstance(payload, dict):
        raise InstanceFormatError("instance file must contain a JSON object")
    if _looks_like_legacy_node_link(payload):
        graph = json_graph.node_link_graph(payload, edges=LEGACY_NODE_LINK_EDGES_KEY)
        metadata = _build_legacy_metadata(instance_path, graph).to_dict()
        return deepcopy(metadata), graph
    if payload.get("format_version") != INSTANCE_FORMAT_VERSION:
        raise InstanceFormatError(
            "unsupported instance format version: {!r}".format(payload.get("format_version"))
        )
    if "metadata" not in payload:
        raise InstanceFormatError("instance file is missing top-level 'metadata'")
    if "graph" not in payload:
        raise InstanceFormatError("instance file is missing top-level 'graph'")

    metadata = _coerce_metadata(payload["metadata"]).to_dict()
    graph = json_graph.node_link_graph(payload["graph"], edges=CANONICAL_NODE_LINK_EDGES_KEY)
    return deepcopy(metadata), graph


def save_instance(
    record_or_graph: Union[InstanceRecord, nx.Graph],
    path: Union[str, Path],
    metadata: Optional[Mapping[str, Any]] = None,
) -> None:
    """Write a canonical instance envelope to disk."""
    instance_path = Path(path)
    if instance_path.suffix == ".col":
        from three_col_circle_code.instances.dimacs_circle import write_dimacs_circle

        graph, normalized_metadata = _coerce_record_or_graph(record_or_graph, metadata)
        write_dimacs_circle(
            InstanceRecord(
                metadata=InstanceMetadata.from_mapping(normalized_metadata),
                graph=graph,
            ),
            instance_path,
        )
        return
    graph, normalized_metadata = _coerce_record_or_graph(record_or_graph, metadata)
    payload = {
        "format_version": INSTANCE_FORMAT_VERSION,
        "metadata": deepcopy(normalized_metadata),
        "graph": _graph_to_node_link_payload(graph),
    }
    instance_path.parent.mkdir(parents=True, exist_ok=True)
    with instance_path.open("w", encoding="utf-8") as outfile:
        json.dump(payload, outfile)


def get_instance_metadata(instance: InstanceRecord) -> Dict[str, Any]:
    """Return a copy of the metadata stored in an InstanceRecord."""
    return instance.metadata.to_dict()


def set_instance_metadata(instance: InstanceRecord, metadata: Mapping[str, Any]) -> InstanceRecord:
    """Return a new InstanceRecord with replaced metadata."""
    return InstanceRecord(metadata=_coerce_metadata(metadata), graph=instance.graph)


def _coerce_metadata(metadata: Mapping[str, Any]) -> InstanceMetadata:
    """Normalize supported metadata inputs to an InstanceMetadata object."""
    if isinstance(metadata, InstanceMetadata):
        return metadata
    if not isinstance(metadata, Mapping):
        raise InstanceFormatError("instance metadata must be a mapping")
    return InstanceMetadata.from_mapping(metadata)


def _normalized_metadata_for_graph(
    graph: nx.Graph, metadata: Mapping[str, Any]
) -> Dict[str, Any]:
    """Copy metadata and overwrite `n` and `m` from the actual graph."""
    instance_metadata = _coerce_metadata(metadata).to_dict()
    instance_metadata["n"] = graph.number_of_nodes()
    instance_metadata["m"] = graph.number_of_edges()
    instance_metadata["average_degree"] = _average_degree(
        graph.number_of_nodes(),
        graph.number_of_edges(),
    )
    return instance_metadata


def _looks_like_legacy_node_link(payload: Mapping[str, Any]) -> bool:
    """Detect the old raw node-link format used in the legacy repository data."""
    return all(key in payload for key in ("directed", "multigraph", "nodes"))


def _graph_to_node_link_payload(graph: nx.Graph) -> Dict[str, Any]:
    """Serialize a graph using the canonical node-link edge key."""
    return json_graph.node_link_data(graph, edges=CANONICAL_NODE_LINK_EDGES_KEY)


def _build_legacy_metadata(path: Path, graph: nx.Graph) -> InstanceMetadata:
    """Derive minimal metadata for a legacy graph file during import."""
    created_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()
    return build_legacy_metadata(
        instance_id=path.stem,
        n=graph.number_of_nodes(),
        m=graph.number_of_edges(),
        family=_infer_legacy_family(path),
        created_at=created_at,
    )


def _infer_legacy_family(path: Path) -> str:
    """Guess the legacy family tag from the file path components."""
    return infer_legacy_family_from_parts(path.parts) or "legacy"


def _average_degree(n_vertices: int, n_edges: int) -> float:
    if n_vertices == 0:
        return 0.0
    return 2.0 * n_edges / n_vertices


def _coerce_record_or_graph(
    record_or_graph: Union[InstanceRecord, nx.Graph],
    metadata: Optional[Mapping[str, Any]],
) -> Tuple[nx.Graph, Dict[str, Any]]:
    """Accept either an InstanceRecord or a graph plus explicit metadata."""
    if isinstance(record_or_graph, InstanceRecord):
        if metadata is not None:
            raise InstanceFormatError(
                "metadata must not be provided separately when saving an InstanceRecord"
            )
        return record_or_graph.graph, _normalized_metadata_for_graph(
            record_or_graph.graph, record_or_graph.metadata.to_dict()
        )
    if metadata is None:
        raise InstanceFormatError("metadata is required when saving a graph directly")
    return record_or_graph, _normalized_metadata_for_graph(record_or_graph, metadata)
