import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.generation.families import (
    generate_seeded_family,
    infer_legacy_family_from_parts,
    legacy_cli_families,
    seeded_families,
)


class GenerationFamiliesTests(unittest.TestCase):
    def test_family_registry_lists_expected_families(self) -> None:
        self.assertEqual(legacy_cli_families(), ("r", "ry", "rc", "rc_fast", "rcy", "rcy_fast", "rccy"))
        self.assertEqual(
            seeded_families(),
            (
                "rc",
                "rc_fast",
                "rcy",
                "rcy_fast",
                "rccy",
                "rccy_tuned",
                "rccy_baseline",
                "rccy_full_sweep_weighted_active",
                "rccy_full_sweep_max_active",
            ),
        )

    def test_generate_seeded_family_returns_graph_and_generator_name(self) -> None:
        graph, generator_name = generate_seeded_family(
            family="rccy_baseline",
            n=6,
            seed=11,
            max_attempts_per_node=10_000,
        )

        self.assertEqual(generator_name, "seeded_random_circle_graph_yes_constructive_baseline")
        self.assertEqual(graph.number_of_nodes(), 6)

    def test_infer_legacy_family_from_parts_prefers_exact_path_token(self) -> None:
        family = infer_legacy_family_from_parts(("eval", "graph_data", "rc_fast", "s", "sample.json"))

        self.assertEqual(family, "rc_fast")

    def test_seeded_generation_rejects_legacy_only_families(self) -> None:
        for family in ("r", "ry"):
            with self.assertRaises(ValueError):
                generate_seeded_family(
                    family=family,
                    n=6,
                    seed=11,
                    max_attempts_per_node=10_000,
                )


if __name__ == "__main__":
    unittest.main()
