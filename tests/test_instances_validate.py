import json
import sys
import tempfile
import unittest
from pathlib import Path

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.instances.io import save_instance
from three_col_circle_code.instances.model import InstanceMetadata, InstanceRecord
from three_col_circle_code.instances.validate import validate_instance, validate_instance_file


class InstanceValidateTests(unittest.TestCase):
    def test_validate_instance_accepts_valid_small_circle_graph(self) -> None:
        graph = nx.Graph()
        graph.add_node(0, label=0, l=0, r=2)
        graph.add_node(1, label=1, l=1, r=3)
        graph.add_edge(0, 1)

        report = validate_instance(graph)

        self.assertTrue(report.ok)
        self.assertEqual(report.errors, [])

    def test_validate_instance_rejects_duplicate_endpoint_positions(self) -> None:
        graph = nx.Graph()
        graph.add_node(0, label=0, l=0, r=2)
        graph.add_node(1, label=1, l=0, r=3)
        graph.add_edge(0, 1)

        report = validate_instance(graph)

        self.assertFalse(report.ok)
        self.assertIn("graph.endpoint_duplicate", {issue.code for issue in report.errors})

    def test_validate_instance_rejects_edge_mismatch(self) -> None:
        graph = nx.Graph()
        graph.add_node(0, label=0, l=0, r=2)
        graph.add_node(1, label=1, l=1, r=3)

        report = validate_instance(graph)

        self.assertFalse(report.ok)
        self.assertIn("graph.edge_mismatch", {issue.code for issue in report.errors})

    def test_validate_instance_checks_metadata_n_m_and_bucket(self) -> None:
        graph = nx.Graph()
        graph.add_node(0, label=0, l=0, r=2)
        graph.add_node(1, label=1, l=1, r=3)
        graph.add_edge(0, 1)
        metadata = {
            "instance_id": "bad-meta",
            "family": "rc",
            "seed": 1,
            "generator": "unit",
            "n": 999,
            "m": 999,
            "bucket": "xl",
            "source": "generated",
            "created_at": "2026-04-13T00:00:00Z",
            "generation_time_seconds": 0.1,
            "max_attempts_per_node": 10_000,
        }

        report = validate_instance(graph, metadata=metadata)

        codes = {issue.code for issue in report.errors}
        self.assertIn("metadata.n_mismatch", codes)
        self.assertIn("metadata.m_mismatch", codes)
        self.assertIn("metadata.bucket_mismatch", codes)

    def test_validate_instance_file_accepts_legacy_node_link_input(self) -> None:
        legacy_payload = {
            "directed": False,
            "multigraph": False,
            "graph": {},
            "nodes": [
                {"id": 0, "label": 0, "l": 0, "r": 2},
                {"id": 1, "label": 1, "l": 1, "r": 3},
            ],
            "links": [{"source": 0, "target": 1}],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "legacy.json"
            path.write_text(json.dumps(legacy_payload), encoding="utf-8")

            report = validate_instance_file(path)

        self.assertTrue(report.ok)

    def test_validate_instance_file_rejects_bad_canonical_metadata(self) -> None:
        graph = nx.Graph()
        graph.add_node(0, label=0, l=0, r=2)
        graph.add_node(1, label=1, l=1, r=3)
        graph.add_edge(0, 1)
        record = InstanceRecord(
            metadata=InstanceMetadata(
                instance_id="bad-canonical",
                family="rc",
                seed=1,
                generator="unit",
                n=1,
                m=0,
                bucket="xl",
                source="generated",
                created_at="2026-04-13T00:00:00Z",
                generation_time_seconds=0.1,
                max_attempts_per_node=10_000,
            ),
            graph=graph,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "instance.json"
            save_instance(record, path)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["metadata"]["bucket"] = "xl"
            payload["metadata"]["n"] = 1
            path.write_text(json.dumps(payload), encoding="utf-8")

            report = validate_instance_file(path)

        self.assertFalse(report.ok)
        self.assertIn("metadata.n_mismatch", {issue.code for issue in report.errors})


if __name__ == "__main__":
    unittest.main()
