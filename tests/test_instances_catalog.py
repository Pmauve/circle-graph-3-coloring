import json
import sys
import tempfile
import unittest
from pathlib import Path

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.instances.catalog import discover_instances, filter_instances
from three_col_circle_code.instances.io import save_instance
from three_col_circle_code.instances.model import InstanceMetadata, InstanceRecord


class InstanceCatalogTests(unittest.TestCase):
    def test_discover_instances_finds_json_files_recursively_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "nested").mkdir()
            first = _write_canonical_instance(root / "b.json", family="rc", n=2, seed=1, source="generated")
            second = _write_canonical_instance(
                root / "nested" / "a.json", family="rcy", n=3, seed=2, source="generated"
            )
            (root / "ignore.txt").write_text("x", encoding="utf-8")

            discovered = discover_instances(root)

        self.assertEqual(discovered, sorted([first, second]))

    def test_discover_instances_returns_single_json_file_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write_canonical_instance(
                Path(tmpdir) / "single.json", family="rc", n=2, seed=1, source="generated"
            )

            discovered = discover_instances(path)

        self.assertEqual(discovered, [path])

    def test_filter_instances_supports_family_bucket_n_source_and_seed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            rc_small = _write_canonical_instance(root / "rc_small.json", family="rc", n=2, seed=10, source="generated")
            rcy_small = _write_canonical_instance(
                root / "rcy_small.json", family="rcy", n=3, seed=11, source="generated"
            )
            rc_legacy_source = _write_canonical_instance(
                root / "rc_legacy_source.json", family="rc", n=2, seed=12, source="legacy-import"
            )

            all_paths = discover_instances(root)

            self.assertEqual(filter_instances(all_paths, family="rc"), [rc_legacy_source, rc_small])
            self.assertEqual(filter_instances(all_paths, buckets=["s"], source="generated"), [rc_small, rcy_small])
            self.assertEqual(filter_instances(all_paths, n_min=3), [rcy_small])
            self.assertEqual(filter_instances(all_paths, seed=12), [rc_legacy_source])
            self.assertEqual(
                filter_instances(all_paths, instance_ids=["rc-k03-n0002-seed10"]),
                [rc_small],
            )

    def test_filter_instances_accepts_legacy_raw_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "rcy"
            root.mkdir()
            legacy_path = root / "legacy_graph.json"
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
            legacy_path.write_text(json.dumps(legacy_payload), encoding="utf-8")

            matches = filter_instances(discover_instances(root), family="rcy", source="legacy")

        self.assertEqual(matches, [legacy_path])


def _write_canonical_instance(path: Path, *, family: str, n: int, seed: int, source: str) -> Path:
    graph = _path_graph_for_n(n)
    record = InstanceRecord(
        metadata=InstanceMetadata(
            instance_id=f"{family}-k03-n{n:04d}-seed{seed}",
            family=family,
            seed=seed,
            generator="test_fixture",
            n=graph.number_of_nodes(),
            m=graph.number_of_edges(),
            bucket="s",
            source=source,
            created_at="2026-04-13T00:00:00Z",
        ),
        graph=graph,
    )
    save_instance(record, path)
    return path


def _path_graph_for_n(n: int) -> nx.Graph:
    graph = nx.Graph()
    for node in range(n):
        graph.add_node(node, label=node, l=node, r=node + n)
    for node in range(n - 1):
        graph.add_edge(node, node + 1)
    return graph


if __name__ == "__main__":
    unittest.main()
