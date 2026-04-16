import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.solvers.sosa.arc_ops import count_active_endpoints_in_arc
from three_col_circle_code.solvers.sosa.colors import ALL_COLOR_MASK
from three_col_circle_code.solvers.sosa.colors import Color, color_to_mask
from three_col_circle_code.solvers.sosa.lemma_37 import (
    construct_lemma_37_partition,
    iter_lemma_37_family,
    is_semi_separated_instance,
)
from three_col_circle_code.solvers.sosa.types import SosaSearchState, SosaStats
from sosa_test_utils import (
    geometry_from_endpoints,
    solve_state_bruteforce,
    state_from_allowed_masks,
    vertex_mask,
)


class SosaLemma37Tests(unittest.TestCase):
    def test_construct_lemma_37_partition_balances_active_endpoints_with_gaps(self) -> None:
        geometry = geometry_from_endpoints(((0, 1), (2, 3), (4, 5), (6, 7)))
        state = SosaSearchState(
            active_vertices_mask=vertex_mask(1, 3),
            allowed_color_masks=(
                ALL_COLOR_MASK,
                ALL_COLOR_MASK,
                ALL_COLOR_MASK,
                ALL_COLOR_MASK,
            ),
        )

        partition = construct_lemma_37_partition(geometry=geometry, state=state)

        self.assertEqual(
            tuple(
                count_active_endpoints_in_arc(
                    geometry=geometry,
                    state=state,
                    partition=partition,
                    arc_name=arc_name,
                )
                for arc_name in ("L", "T", "R", "B")
            ),
            (1, 1, 1, 1),
        )

    def test_compute_lemma_37_family_returns_semi_separated_instances(self) -> None:
        geometry = geometry_from_endpoints(((0, 5), (1, 4), (2, 7), (3, 6)))
        state = state_from_allowed_masks(
            ALL_COLOR_MASK,
            ALL_COLOR_MASK,
            ALL_COLOR_MASK,
            ALL_COLOR_MASK,
        )
        stats = SosaStats()

        family = list(iter_lemma_37_family(geometry=geometry, state=state, stats=stats))

        self.assertEqual(len(family), 6)
        self.assertEqual(stats.lemma_36_calls, 1)
        for semi_instance in family:
            self.assertTrue(is_semi_separated_instance(geometry=geometry, semi_instance=semi_instance))
            self.assertEqual(
                semi_instance.state.active_vertices_mask & ~state.active_vertices_mask,
                0,
            )
            for vertex_index in range(geometry.n_vertices):
                self.assertEqual(
                    semi_instance.state.allowed_color_masks[vertex_index]
                    & ~state.allowed_color_masks[vertex_index],
                    0,
                )
            self.assertGreaterEqual(
                count_active_endpoints_in_arc(
                    geometry=geometry,
                    state=state,
                    partition=semi_instance.partition,
                    arc_name="L",
                ),
                state.n_active_vertices // 2,
            )
            self.assertGreaterEqual(
                count_active_endpoints_in_arc(
                    geometry=geometry,
                    state=state,
                    partition=semi_instance.partition,
                    arc_name="R",
                ),
                state.n_active_vertices // 2,
            )

    def test_compute_lemma_37_family_preserves_yes_instance_existence(self) -> None:
        geometry = geometry_from_endpoints(((0, 5), (1, 4), (2, 7), (3, 6)))
        state = state_from_allowed_masks(
            ALL_COLOR_MASK,
            ALL_COLOR_MASK,
            ALL_COLOR_MASK,
            ALL_COLOR_MASK,
        )
        stats = SosaStats()

        family = list(iter_lemma_37_family(geometry=geometry, state=state, stats=stats))

        self.assertTrue(solve_state_bruteforce(geometry, state))
        self.assertTrue(
            any(solve_state_bruteforce(geometry, semi_instance.state) for semi_instance in family)
        )

    def test_compute_lemma_37_family_preserves_no_instance_existence(self) -> None:
        geometry = geometry_from_endpoints(((0, 5), (1, 4), (2, 7), (3, 6)))
        red_only = color_to_mask(Color.RED)
        state = state_from_allowed_masks(red_only, red_only, red_only, red_only)
        stats = SosaStats()

        family = list(iter_lemma_37_family(geometry=geometry, state=state, stats=stats))

        self.assertFalse(solve_state_bruteforce(geometry, state))
        self.assertEqual(family, [])


if __name__ == "__main__":
    unittest.main()
