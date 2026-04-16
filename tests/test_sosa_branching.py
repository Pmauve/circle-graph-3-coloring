import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.solvers.sosa.colors import ALL_COLOR_MASK
from three_col_circle_code.solvers.sosa.colors import Color, color_to_mask
from three_col_circle_code.solvers.sosa.lemma_36 import iter_lemma_36_family
from three_col_circle_code.solvers.sosa.types import SosaStats
from sosa_test_utils import (
    geometry_from_endpoints,
    solve_state_bruteforce,
    state_from_allowed_masks,
    vertex_mask,
)


class SosaLemma36Tests(unittest.TestCase):
    def test_branch_lemma_36_returns_six_distinct_states_on_k22(self) -> None:
        geometry = geometry_from_endpoints(((0, 5), (1, 4), (2, 7), (3, 6)))
        state = state_from_allowed_masks(
            ALL_COLOR_MASK,
            ALL_COLOR_MASK,
            ALL_COLOR_MASK,
            ALL_COLOR_MASK,
        )
        stats = SosaStats()

        family = list(
            iter_lemma_36_family(
                geometry=geometry,
                state=state,
                x_vertices_mask=vertex_mask(0, 1),
                y_vertices_mask=vertex_mask(2, 3),
                stats=stats,
            )
        )

        self.assertEqual(len(family), 6)
        self.assertEqual(stats.lemma_36_calls, 1)
        for reduced_result in family:
            active_x = reduced_result.state.active_vertices_mask & vertex_mask(0, 1)
            active_y = reduced_result.state.active_vertices_mask & vertex_mask(2, 3)
            self.assertTrue(active_x == 0 or active_y == 0)

    def test_branch_lemma_36_deduplicates_empty_set_branches(self) -> None:
        geometry = geometry_from_endpoints(((0, 1), (2, 3), (4, 5), (6, 7)))
        state = state_from_allowed_masks(
            ALL_COLOR_MASK,
            ALL_COLOR_MASK,
            ALL_COLOR_MASK,
            ALL_COLOR_MASK,
        )
        stats = SosaStats()

        family = list(
            iter_lemma_36_family(
                geometry=geometry,
                state=state,
                x_vertices_mask=0,
                y_vertices_mask=0,
                stats=stats,
            )
        )

        self.assertEqual(len(family), 1)
        self.assertEqual(family[0].state, state)
        self.assertEqual(family[0].fixed_colors, ())

    def test_branch_lemma_36_preserves_yes_instance_existence(self) -> None:
        geometry = geometry_from_endpoints(((0, 5), (1, 4), (2, 7), (3, 6)))
        state = state_from_allowed_masks(
            ALL_COLOR_MASK,
            ALL_COLOR_MASK,
            ALL_COLOR_MASK,
            ALL_COLOR_MASK,
        )
        stats = SosaStats()

        family = list(
            iter_lemma_36_family(
                geometry=geometry,
                state=state,
                x_vertices_mask=vertex_mask(0, 1),
                y_vertices_mask=vertex_mask(2, 3),
                stats=stats,
            )
        )

        self.assertTrue(solve_state_bruteforce(geometry, state))
        self.assertTrue(any(solve_state_bruteforce(geometry, child.state) for child in family))

    def test_branch_lemma_36_preserves_no_instance_existence(self) -> None:
        geometry = geometry_from_endpoints(((0, 5), (1, 4), (2, 7), (3, 6)))
        red_only = color_to_mask(Color.RED)
        state = state_from_allowed_masks(red_only, red_only, red_only, red_only)
        stats = SosaStats()

        family = list(
            iter_lemma_36_family(
                geometry=geometry,
                state=state,
                x_vertices_mask=vertex_mask(0, 1),
                y_vertices_mask=vertex_mask(2, 3),
                stats=stats,
            )
        )

        self.assertFalse(solve_state_bruteforce(geometry, state))
        self.assertFalse(any(solve_state_bruteforce(geometry, child.state) for child in family))
        self.assertEqual(family, [])


if __name__ == "__main__":
    unittest.main()
