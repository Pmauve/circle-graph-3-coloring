import json
import sys
import tempfile
import unittest
from pathlib import Path

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.instances.io import (
    get_instance_metadata,
    load_instance,
    load_instance_envelope,
    save_instance,
)
from three_col_circle_code.instances.model import (
    CANONICAL_NODE_LINK_EDGES_KEY,
    INSTANCE_FORMAT_VERSION,
    InstanceMetadata,
    InstanceRecord,
)


class InstanceIoTests(unittest.TestCase):
    def test_save_and_load_round_trip(self) -> None:
        graph = nx.Graph()
        graph.add_node(0, label=0, l=0, r=3)
        graph.add_node(1, label=1, l=1, r=2)
        graph.add_edge(0, 1)
        metadata = {
            "instance_id": "sample-instance",
            "family": "rc",
            "seed": 7,
            "generator": "unit_test",
            "n": -1,
            "m": -1,
            "bucket": "s",
            "source": "generated",
            "created_at": "2026-04-13T10:00:00Z",
            "generation_time_seconds": 0.125,
            "max_attempts_per_node": 321,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "instance.json"
            save_instance(graph, path, metadata)
            payload = json.loads(path.read_text(encoding="utf-8"))

            loaded = load_instance(path)

        self.assertEqual(payload["graph"]["graph"], {})
        self.assertIn(CANONICAL_NODE_LINK_EDGES_KEY, payload["graph"])
        loaded_metadata = get_instance_metadata(loaded)
        self.assertEqual(loaded_metadata["instance_id"], "sample-instance")
        self.assertEqual(loaded_metadata["n"], 2)
        self.assertEqual(loaded_metadata["m"], 1)
        self.assertEqual(loaded_metadata["generation_time_seconds"], 0.125)
        self.assertEqual(loaded_metadata["max_attempts_per_node"], 321)
        self.assertEqual(loaded.graph.nodes[0]["l"], 0)
        self.assertEqual(loaded.graph.nodes[1]["r"], 2)
        self.assertEqual(set(loaded.graph.edges()), {(0, 1)})

    def test_load_instance_envelope_returns_metadata_and_graph_separately(self) -> None:
        payload = {
            "format_version": INSTANCE_FORMAT_VERSION,
            "metadata": {
                "instance_id": "tiny",
                "family": "paper",
                "seed": None,
                "generator": "manual",
                "n": 1,
                "m": 0,
                "bucket": "s",
                "source": "handcrafted",
                "created_at": "2026-04-13T10:00:00Z",
                "generation_time_seconds": 0.0,
                "max_attempts_per_node": 10_000,
            },
            "graph": {
                "directed": False,
                "multigraph": False,
                "graph": {},
                "nodes": [{"id": 0, "label": 0, "l": 0, "r": 1}],
                "edges": [],
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "instance.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            metadata, graph = load_instance_envelope(path)

        self.assertEqual(metadata["instance_id"], "tiny")
        self.assertEqual(metadata["generation_time_seconds"], 0.0)
        self.assertEqual(metadata["max_attempts_per_node"], 10_000)
        self.assertEqual(graph.nodes[0]["label"], 0)

    def test_save_accepts_instance_record(self) -> None:
        graph = nx.Graph()
        graph.add_node(0, label=0, l=0, r=1)
        record = InstanceRecord(
            metadata=InstanceMetadata(
                instance_id="record",
                family="paper",
                seed=None,
                generator="manual",
                n=0,
                m=0,
                bucket="s",
                source="handcrafted",
                created_at="2026-04-13T10:00:00Z",
                generation_time_seconds=0.0,
                max_attempts_per_node=10_000,
            ),
            graph=graph,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "record.json"
            save_instance(record, path)
            loaded = load_instance(path)

        self.assertEqual(loaded.metadata.instance_id, "record")
        self.assertEqual(loaded.metadata.generation_time_seconds, 0.0)
        self.assertEqual(loaded.metadata.max_attempts_per_node, 10_000)
        self.assertEqual(loaded.graph.number_of_nodes(), 1)

    def test_load_accepts_legacy_raw_node_link_files(self) -> None:
        legacy_payload = {
            "directed": False,
            "multigraph": False,
            "graph": {},
            "nodes": [{"id": 0, "label": 0, "l": 0, "r": 1}],
            "links": [],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "legacy.json"
            path.write_text(json.dumps(legacy_payload), encoding="utf-8")
            loaded = load_instance(path)

        metadata = get_instance_metadata(loaded)
        self.assertEqual(metadata["instance_id"], "legacy")
        self.assertEqual(metadata["family"], "legacy")
        self.assertEqual(metadata["source"], "legacy")
        self.assertEqual(metadata["n"], 1)
        self.assertEqual(metadata["m"], 0)
        self.assertIsNone(metadata["generation_time_seconds"])
        self.assertIsNone(metadata["max_attempts_per_node"])


if __name__ == "__main__":
    unittest.main()
