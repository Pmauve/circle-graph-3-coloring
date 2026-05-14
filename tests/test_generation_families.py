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
                "rccy_alpha",
                "rccy_alpha0",
                "rccy_alpha1",
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

    def test_generate_seeded_family_accepts_larger_palette_for_k_color_yes_families(self) -> None:
        for family in (
            "rcy_fast",
            "rccy",
            "rccy_tuned",
            "rccy_baseline",
            "rccy_full_sweep_weighted_active",
            "rccy_full_sweep_max_active",
        ):
            graph, _generator_name = generate_seeded_family(
                family=family,
                n=6,
                seed=11,
                max_attempts_per_node=10_000,
                num_colors=4,
            )

            self.assertEqual(graph.number_of_nodes(), 6, msg=f"{family} did not generate")

    def test_generate_seeded_family_rejects_larger_palette_for_non_k_aware_families(self) -> None:
        for family in ("rc", "rc_fast", "rcy"):
            with self.assertRaisesRegex(ValueError, "num_colors=4"):
                generate_seeded_family(
                    family=family,
                    n=6,
                    seed=11,
                    max_attempts_per_node=10_000,
                    num_colors=4,
                )

    def test_generate_seeded_family_rejects_invalid_num_colors(self) -> None:
        with self.assertRaisesRegex(ValueError, "num_colors"):
            generate_seeded_family(
                family="rcy_fast",
                n=6,
                seed=11,
                max_attempts_per_node=10_000,
                num_colors=0,
            )

    def test_generate_seeded_family_rejects_native_only_families(self) -> None:
        for family in ("rccy_alpha", "rccy_alpha0", "rccy_alpha1"):
            with self.assertRaisesRegex(ValueError, "native instance generation"):
                generate_seeded_family(
                    family=family,
                    n=6,
                    seed=11,
                    max_attempts_per_node=10_000,
                )

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
