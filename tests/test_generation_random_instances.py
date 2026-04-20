import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.generation.random_instances import (
    generate_instance,
    generate_many,
    write_instance,
)
from three_col_circle_code.instances.io import load_instance
from three_col_circle_code.instances.validate import validate_instance, validate_instance_file


class RandomInstanceGenerationTests(unittest.TestCase):
    def test_generate_instance_is_reproducible_for_same_seed(self) -> None:
        first = generate_instance(family="rc", n=8, seed=17)
        second = generate_instance(family="rc", n=8, seed=17)

        self.assertEqual(_graph_signature(first.graph), _graph_signature(second.graph))
        self.assertEqual(first.metadata.instance_id, second.metadata.instance_id)
        self.assertEqual(first.metadata.m, second.metadata.m)
        self.assertIsNotNone(first.metadata.generation_time_seconds)
        self.assertGreaterEqual(first.metadata.generation_time_seconds, 0.0)
        self.assertEqual(first.metadata.max_attempts_per_node, 10_000)

    def test_generate_rcy_instance_validates(self) -> None:
        record = generate_instance(family="rcy", n=8, seed=29)

        report = validate_instance(record.graph, metadata=record.metadata.to_dict())

        self.assertTrue(report.ok)

    def test_generate_rcy_fast_instance_validates(self) -> None:
        record = generate_instance(family="rcy_fast", n=8, seed=29)

        report = validate_instance(record.graph, metadata=record.metadata.to_dict())

        self.assertTrue(report.ok)
        self.assertEqual(record.metadata.family, "rcy_fast")
        self.assertEqual(record.metadata.generator, "seeded_random_circle_graph_yes_fast_legacy_like")
        self.assertTrue(all("level" not in attrs for _, attrs in record.graph.nodes(data=True)))
        self.assertTrue(all("color" not in attrs for _, attrs in record.graph.nodes(data=True)))

    def test_generate_rc_fast_instance_validates(self) -> None:
        record = generate_instance(family="rc_fast", n=8, seed=31)

        report = validate_instance(record.graph, metadata=record.metadata.to_dict())

        self.assertTrue(report.ok)
        self.assertEqual(record.metadata.family, "rc_fast")
        self.assertEqual(record.metadata.generator, "seeded_random_circle_graph_fast_legacy_like")
        self.assertTrue(all("level" not in attrs for _, attrs in record.graph.nodes(data=True)))

    def test_generate_rc_fast_matches_rc_for_same_seed(self) -> None:
        legacy_record = generate_instance(family="rc", n=8, seed=17)
        fast_record = generate_instance(family="rc_fast", n=8, seed=17)

        self.assertEqual(_graph_signature(legacy_record.graph), _graph_signature(fast_record.graph))
        self.assertEqual(legacy_record.metadata.seed, fast_record.metadata.seed)
        self.assertEqual(legacy_record.metadata.n, fast_record.metadata.n)
        self.assertEqual(legacy_record.metadata.m, fast_record.metadata.m)

    def test_generate_rcy_fast_matches_rcy_for_same_seed(self) -> None:
        legacy_record = generate_instance(family="rcy", n=8, seed=17)
        fast_record = generate_instance(family="rcy_fast", n=8, seed=17)

        self.assertEqual(_graph_signature(legacy_record.graph), _graph_signature(fast_record.graph))
        self.assertEqual(legacy_record.metadata.seed, fast_record.metadata.seed)
        self.assertEqual(legacy_record.metadata.n, fast_record.metadata.n)
        self.assertEqual(legacy_record.metadata.m, fast_record.metadata.m)

    def test_generate_constructive_instances_validate(self) -> None:
        expected_generators = {
            "rccy": "seeded_random_circle_graph_yes_constructive_tuned",
            "rccy_tuned": "seeded_random_circle_graph_yes_constructive_tuned",
            "rccy_baseline": "seeded_random_circle_graph_yes_constructive_baseline",
            "rccy_full_sweep_weighted_active": (
                "seeded_random_circle_graph_yes_constructive_full_sweep_weighted_active"
            ),
            "rccy_full_sweep_max_active": "seeded_random_circle_graph_yes_constructive_full_sweep_max_active",
        }

        for family, expected_generator in expected_generators.items():
            record = generate_instance(family=family, n=8, seed=29)
            report = validate_instance(record.graph, metadata=record.metadata.to_dict())

            self.assertTrue(report.ok, msg=f"{family} did not validate")
            self.assertEqual(record.metadata.family, family)
            self.assertEqual(record.metadata.generator, expected_generator)
            self.assertTrue(all("level" not in attrs for _, attrs in record.graph.nodes(data=True)))
            self.assertTrue(all("color" not in attrs for _, attrs in record.graph.nodes(data=True)))

    def test_generate_rccy_alias_matches_tuned_for_same_seed(self) -> None:
        alias_record = generate_instance(family="rccy", n=8, seed=17)
        tuned_record = generate_instance(family="rccy_tuned", n=8, seed=17)

        self.assertEqual(_graph_signature(alias_record.graph), _graph_signature(tuned_record.graph))
        self.assertEqual(alias_record.metadata.seed, tuned_record.metadata.seed)
        self.assertEqual(alias_record.metadata.n, tuned_record.metadata.n)
        self.assertEqual(alias_record.metadata.m, tuned_record.metadata.m)

    def test_generate_many_uses_sequential_derived_seeds(self) -> None:
        records = generate_many(family="rc", n=6, root_seed=10, count=3)

        self.assertEqual([record.metadata.seed for record in records], [10, 11, 12])
        self.assertEqual(len({record.metadata.instance_id for record in records}), 3)
        self.assertEqual(
            [record.metadata.max_attempts_per_node for record in records],
            [10_000, 10_000, 10_000],
        )

    def test_generate_many_rc_fast_uses_sequential_derived_seeds(self) -> None:
        records = generate_many(family="rc_fast", n=6, root_seed=10, count=3)

        self.assertEqual([record.metadata.seed for record in records], [10, 11, 12])
        self.assertEqual(len({record.metadata.instance_id for record in records}), 3)

    def test_generate_many_rcy_fast_uses_sequential_derived_seeds(self) -> None:
        records = generate_many(family="rcy_fast", n=6, root_seed=10, count=3)

        self.assertEqual([record.metadata.seed for record in records], [10, 11, 12])
        self.assertEqual(len({record.metadata.instance_id for record in records}), 3)

    def test_generate_many_rccy_uses_sequential_derived_seeds(self) -> None:
        records = generate_many(family="rccy", n=6, root_seed=10, count=3)

        self.assertEqual([record.metadata.seed for record in records], [10, 11, 12])
        self.assertEqual(len({record.metadata.instance_id for record in records}), 3)

    def test_generate_instance_rejects_legacy_only_family(self) -> None:
        for family in ("r", "ry"):
            with self.assertRaises(ValueError):
                generate_instance(family=family, n=8, seed=17)

    def test_write_instance_saves_canonical_envelope(self) -> None:
        record = generate_instance(family="rc", n=6, seed=5)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            path = write_instance(record, output_dir)
            payload = json.loads(path.read_text(encoding="utf-8"))
            loaded = load_instance(path)
            report = validate_instance_file(path)

        self.assertEqual(
            path,
            output_dir / record.metadata.family / record.metadata.bucket / f"{record.metadata.instance_id}.json",
        )
        self.assertIn("metadata", payload)
        self.assertIn("graph", payload)
        self.assertEqual(loaded.metadata.instance_id, record.metadata.instance_id)
        self.assertIsNotNone(loaded.metadata.generation_time_seconds)
        self.assertGreaterEqual(loaded.metadata.generation_time_seconds, 0.0)
        self.assertEqual(loaded.metadata.max_attempts_per_node, 10_000)
        self.assertTrue(report.ok)

    def test_generate_instance_records_custom_attempt_limit_in_metadata(self) -> None:
        record = generate_instance(family="rc_fast", n=8, seed=17, max_attempts_per_node=321)

        self.assertEqual(record.metadata.max_attempts_per_node, 321)
        self.assertIsNotNone(record.metadata.generation_time_seconds)
        self.assertGreaterEqual(record.metadata.generation_time_seconds, 0.0)


def _graph_signature(graph) -> tuple:
    node_signature = tuple(
        sorted((node_id, attrs["label"], attrs["l"], attrs["r"]) for node_id, attrs in graph.nodes(data=True))
    )
    edge_signature = tuple(sorted(tuple(sorted(edge)) for edge in graph.edges()))
    return node_signature, edge_signature


if __name__ == "__main__":
    unittest.main()
