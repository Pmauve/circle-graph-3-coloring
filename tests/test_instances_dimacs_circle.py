import sys
import tempfile
import unittest
from pathlib import Path

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.instances.dimacs_circle import (
    export_dimacs_circle_in_place,
    export_dimacs_circle_tree,
    main,
    read_dimacs_circle,
    write_dimacs_circle,
)
from three_col_circle_code.instances.io import save_instance
from three_col_circle_code.instances.model import InstanceFormatError, InstanceMetadata, InstanceRecord


class DimacsCircleTests(unittest.TestCase):
    def test_write_dimacs_circle_uses_wrapped_chord_endpoint_order(self) -> None:
        record = _sample_record()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.col"
            write_dimacs_circle(record, path, wrap=4)
            text = path.read_text(encoding="utf-8")

        self.assertIn("c hord endpoint order START\n", text)
        self.assertIn("c instance id sample\n", text)
        self.assertIn("c family rcy\n", text)
        self.assertIn("c seed 11\n", text)
        self.assertIn("c n 4\n", text)
        self.assertIn("c m 2\n", text)
        self.assertIn("c average degree 1\n", text)
        self.assertIn("c num colors 3\n", text)
        self.assertIn("c source generated\n", text)
        self.assertIn("c generator unit\n", text)
        self.assertIn("c created at 2026-05-04T00:00:00Z\n", text)
        self.assertIn("c generation time seconds none\n", text)
        self.assertIn("c max attempts per node none\n", text)
        self.assertIn("c 1 2 1 2\n", text)
        self.assertIn("c 3 4 3 4\n", text)
        self.assertIn("c hord endpoint order END\n", text)
        self.assertIn("p edge 4 2\n", text)
        self.assertIn("e 1 2\n", text)
        self.assertIn("e 3 4\n", text)

    def test_write_dimacs_circle_defaults_to_clisat_friendly_bytes(self) -> None:
        record = _noncrossing_record(40)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.col"
            write_dimacs_circle(record, path)
            data = path.read_bytes()
            text = data.decode("utf-8")

        self.assertNotIn(b"\r\n", data)
        circle_lines = _chord_endpoint_order_lines(text)
        self.assertGreater(len(circle_lines), 2)
        self.assertTrue(all(len(line.split()) <= 32 for line in circle_lines))

    def test_read_dimacs_circle_reconstructs_graph_from_wrapped_order(self) -> None:
        text = "\n".join(
            [
                "c instance id wrapped",
                "c hord endpoint order START",
                "c 1 2 1 2",
                "c 3 4 3 4",
                "c hord endpoint order END",
                "p edge 4 2",
                "e 1 2",
                "e 3 4",
                "",
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "wrapped.col"
            path.write_text(text, encoding="utf-8")
            record = read_dimacs_circle(path)

        self.assertEqual(record.metadata.instance_id, "wrapped")
        self.assertEqual(record.graph.nodes[1]["l"], 0)
        self.assertEqual(record.graph.nodes[1]["r"], 2)
        self.assertEqual(set(record.graph.edges()), {(1, 2), (3, 4)})

    def test_round_trip_preserves_circle_graph_structure(self) -> None:
        record = _sample_record()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "roundtrip.col"
            write_dimacs_circle(record, path, wrap=64)
            loaded = read_dimacs_circle(path)

        loaded_order = [
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        ]
        for node_id, attrs in loaded.graph.nodes(data=True):
            loaded_order[attrs["l"]] = node_id
            loaded_order[attrs["r"]] = node_id

        self.assertEqual(loaded_order, [1, 2, 1, 2, 3, 4, 3, 4])
        self.assertEqual(set(loaded.graph.edges()), {(1, 2), (3, 4)})

    def test_read_dimacs_circle_rejects_bad_endpoint_counts(self) -> None:
        text = "\n".join(
            [
                "c hord endpoint order START",
                "c 1 2 1 3 3 3",
                "c hord endpoint order END",
                "p edge 3 0",
                "",
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "bad.col"
            path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(InstanceFormatError, "exactly twice"):
                read_dimacs_circle(path)

    def test_read_dimacs_circle_rejects_edge_mismatch(self) -> None:
        text = "\n".join(
            [
                "c hord endpoint order START",
                "c 1 2 1 2",
                "c hord endpoint order END",
                "p edge 2 0",
                "",
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "mismatch.col"
            path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(InstanceFormatError, "edge_mismatch"):
                read_dimacs_circle(path)

    def test_read_dimacs_circle_rejects_comments_inside_chord_endpoint_order_block(self) -> None:
        text = "\n".join(
            [
                "c hord endpoint order START",
                "c 1 2 1",
                "c arbitrary comment",
                "c 2",
                "c hord endpoint order END",
                "p edge 2 1",
                "e 1 2",
                "",
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "comment.col"
            path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(InstanceFormatError, "expected integer"):
                read_dimacs_circle(path)

    def test_read_dimacs_circle_rejects_duplicate_blocks(self) -> None:
        text = "\n".join(
            [
                "c hord endpoint order START",
                "c 1 1",
                "c hord endpoint order END",
                "c hord endpoint order START",
                "c 1 1",
                "c hord endpoint order END",
                "p edge 1 0",
                "",
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "duplicate.col"
            path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(InstanceFormatError, "duplicate chord endpoint order block"):
                read_dimacs_circle(path)

    def test_export_dimacs_circle_tree_preserves_relative_paths(self) -> None:
        record = _sample_record()

        with tempfile.TemporaryDirectory() as tmpdir:
            input_root = Path(tmpdir) / "instances"
            output_root = Path(tmpdir) / "dimacs"
            save_instance(record, input_root / "rcy" / "s" / "sample.json")
            output_paths = export_dimacs_circle_tree(input_root, output_root, wrap=64)

        self.assertEqual([path.relative_to(output_root) for path in output_paths], [Path("rcy/s/sample.col")])

    def test_export_dimacs_circle_in_place_writes_sibling_col_files(self) -> None:
        record = _sample_record()

        with tempfile.TemporaryDirectory() as tmpdir:
            input_root = Path(tmpdir) / "instances"
            json_path = input_root / "rcy" / "s" / "sample.json"
            save_instance(record, json_path)
            output_paths = export_dimacs_circle_in_place(input_root, wrap=64)
            loaded = read_dimacs_circle(json_path.with_suffix(".col"))

        self.assertEqual(output_paths, [json_path.with_suffix(".col")])
        self.assertEqual(set(loaded.graph.edges()), {(1, 2), (3, 4)})

    def test_cli_without_output_exports_next_to_json(self) -> None:
        record = _sample_record()

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "sample.json"
            save_instance(record, json_path)
            exit_code = main(["--input", str(json_path), "--wrap", "64"])
            col_path = json_path.with_suffix(".col")

            self.assertEqual(exit_code, 0)
            self.assertTrue(col_path.exists())
            self.assertEqual(set(read_dimacs_circle(col_path).graph.edges()), {(1, 2), (3, 4)})


def _sample_record() -> InstanceRecord:
    graph = nx.Graph()
    graph.add_node(0, label=0, l=0, r=2)
    graph.add_node(1, label=1, l=1, r=3)
    graph.add_node(2, label=2, l=4, r=6)
    graph.add_node(3, label=3, l=5, r=7)
    graph.add_edge(0, 1)
    graph.add_edge(2, 3)
    metadata = InstanceMetadata(
        instance_id="sample",
        family="rcy",
        seed=11,
        generator="unit",
        n=4,
        m=2,
        bucket="s",
        source="generated",
        created_at="2026-05-04T00:00:00Z",
    )
    return InstanceRecord(metadata=metadata, graph=graph)


def _noncrossing_record(n: int) -> InstanceRecord:
    graph = nx.Graph()
    for node in range(n):
        graph.add_node(node, label=node, l=2 * node, r=2 * node + 1)
    metadata = InstanceMetadata(
        instance_id=f"noncrossing-{n}",
        family="noncrossing",
        seed=1,
        generator="test",
        n=n,
        m=0,
        bucket="s",
        source="generated",
        created_at="2026-05-04T00:00:00Z",
    )
    return InstanceRecord(metadata=metadata, graph=graph)


def _chord_endpoint_order_lines(text: str) -> list[str]:
    lines = text.splitlines()
    start = lines.index("c hord endpoint order START") + 1
    end = lines.index("c hord endpoint order END")
    return [line.removeprefix("c ") for line in lines[start:end]]


if __name__ == "__main__":
    unittest.main()
