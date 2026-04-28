import argparse
from datetime import UTC, datetime
import os
from pathlib import Path
from time import perf_counter
from typing import Iterable, Optional

import networkx as nx

from three_col_circle_code.generation.families import (
    generate_seeded_family,
    seeded_families,
)
from three_col_circle_code.instances.io import load_instance, save_instance
from three_col_circle_code.instances.model import InstanceFormatError, InstanceMetadata, InstanceRecord, bucket_for_n
from three_col_circle_code.instances.validate import validate_instance


SUPPORTED_FAMILIES = seeded_families()


def generate_instance(
    *,
    family: str,
    n: int,
    seed: int,
    source: str = "generated",
    max_attempts_per_node: int = 10_000,
) -> InstanceRecord:
    """Generate one seeded canonical circle-graph instance."""
    _validate_generation_request(family=family, n=n, max_attempts_per_node=max_attempts_per_node)
    start_time = perf_counter()
    graph, generator_name = generate_seeded_family(
        family=family,
        n=n,
        seed=seed,
        max_attempts_per_node=max_attempts_per_node,
    )
    generation_time_seconds = perf_counter() - start_time
    graph = _to_canonical_graph(graph)
    metadata = InstanceMetadata(
        instance_id=_instance_id(family=family, n=n, seed=seed),
        family=family,
        seed=seed,
        generator=generator_name,
        n=graph.number_of_nodes(),
        m=graph.number_of_edges(),
        bucket=bucket_for_n(n),
        source=source,
        created_at=datetime.now(UTC).isoformat(),
        generation_time_seconds=generation_time_seconds,
        max_attempts_per_node=max_attempts_per_node,
    )
    return InstanceRecord(metadata=metadata, graph=graph)


def generate_many(
    *,
    family: str,
    n: int,
    root_seed: int,
    count: int,
    source: str = "generated",
    max_attempts_per_node: int = 10_000,
) -> list[InstanceRecord]:
    """Generate multiple seeded instances using deterministic derived seeds."""
    if count < 1:
        raise ValueError("count must be at least 1")
    return [
        generate_instance(
            family=family,
            n=n,
            seed=root_seed + index,
            source=source,
            max_attempts_per_node=max_attempts_per_node,
        )
        for index in range(count)
    ]


def write_instance(record: InstanceRecord, output_dir: Path, *, atomic: bool = False) -> Path:
    """Save a generated instance under its deterministic instance id."""
    path = instance_output_path(record, output_dir)
    return write_instance_to_path(record, path, atomic=atomic)


def instance_output_path(record: InstanceRecord, output_dir: Path) -> Path:
    """Return the deterministic canonical path for a generated instance."""
    return (
        Path(output_dir)
        / record.metadata.family
        / record.metadata.bucket
        / f"{record.metadata.instance_id}.json"
    )


def write_instance_to_path(record: InstanceRecord, path: Path, *, atomic: bool = False) -> Path:
    """Save a generated instance to an explicit path."""
    instance_path = Path(path)
    if not atomic:
        save_instance(record, instance_path)
        return instance_path

    instance_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = instance_path.with_name(f".{instance_path.name}.tmp.{os.getpid()}")
    try:
        save_instance(record, tmp_path)
        loaded = load_instance(tmp_path)
        validation = validate_instance(loaded.graph, metadata=loaded.metadata.to_dict())
        if not validation.ok:
            errors = [{"code": issue.code, "message": issue.message} for issue in validation.errors]
            raise ValueError(f"generated instance did not validate: {errors}")
        tmp_path.replace(instance_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    return instance_path


def main(argv: Optional[Iterable[str]] = None) -> int:
    """Generate canonical instance files from the command line."""
    parser = argparse.ArgumentParser(description="Generate seeded canonical circle-graph instances.")
    parser.add_argument("--family", required=True, choices=sorted(SUPPORTED_FAMILIES))
    parser.add_argument("--n", required=True, type=int)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--output-dir", type=Path, default=Path("eval") / "instances")
    parser.add_argument("--source", default="generated")
    parser.add_argument("--max-attempts-per-node", type=int, default=10_000)
    args = parser.parse_args(list(argv) if argv is not None else None)

    records = generate_many(
        family=args.family,
        n=args.n,
        root_seed=args.seed,
        count=args.count,
        source=args.source,
        max_attempts_per_node=args.max_attempts_per_node,
    )
    for record in records:
        path = write_instance(record, args.output_dir)
        print(path)
    return 0


def _to_canonical_graph(graph: nx.Graph) -> nx.Graph:
    canonical = nx.Graph()
    canonical.add_edges_from(graph.edges())
    for node_id, attrs in graph.nodes(data=True):
        canonical.add_node(
            node_id,
            label=attrs.get("label", node_id),
            l=attrs["l"],
            r=attrs["r"],
        )
    return canonical


def _instance_id(*, family: str, n: int, seed: int) -> str:
    return f"{family}-n{n:04d}-seed{seed}"


def _validate_generation_request(*, family: str, n: int, max_attempts_per_node: int) -> None:
    if family not in SUPPORTED_FAMILIES:
        raise ValueError(f"unsupported family {family!r}; expected one of {sorted(SUPPORTED_FAMILIES)}")
    if n < 1:
        raise ValueError("n must be at least 1")
    if max_attempts_per_node < 1:
        raise ValueError("max_attempts_per_node must be at least 1")


if __name__ == "__main__":
    raise SystemExit(main())
