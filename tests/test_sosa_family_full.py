import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.solvers.sosa.colors import ALL_COLOR_MASK
from three_col_circle_code.solvers.sosa.colors import Color, color_to_mask
from three_col_circle_code.solvers.sosa.lemma_37 import is_semi_separated_instance
from three_col_circle_code.solvers.sosa.lemma_38 import (
    is_fully_separated_instance,
    iter_lemma_33_family,
    iter_lemma_38_family,
)
from three_col_circle_code.solvers.sosa.partition import CirclePartition
from three_col_circle_code.solvers.sosa.types import SemiSeparatedInstance, SosaStats
from sosa_test_utils import (
    geometry_from_endpoints,
    solve_state_bruteforce,
    state_from_allowed_masks,
)


class SosaLemma38Tests(unittest.TestCase):
    def test_compute_lemma_38_family_handles_x_zero_base_case(self) -> None:
        geometry = geometry_from_endpoints(((0, 1), (2, 3)))
        state = state_from_allowed_masks(ALL_COLOR_MASK, ALL_COLOR_MASK)
        semi_instance = SemiSeparatedInstance(
            state=state,
            partition=CirclePartition(
                n_endpoints=4,
                left_boundary=0,
                top_boundary=2,
                right_boundary=2,
                bottom_boundary=0,
            ),
        )
        stats = SosaStats()

        family = list(iter_lemma_38_family(geometry=geometry, semi_instance=semi_instance, stats=stats))

        self.assertEqual(len(family), 1)
        self.assertTrue(is_fully_separated_instance(geometry=geometry, full_instance=family[0]))
        self.assertEqual(family[0].state, state)
        self.assertEqual(family[0].partition, semi_instance.partition)

    def test_compute_lemma_38_family_handles_x_one_case(self) -> None:
        geometry = geometry_from_endpoints(((0, 1), (2, 3), (4, 5)))
        state = state_from_allowed_masks(ALL_COLOR_MASK, ALL_COLOR_MASK, ALL_COLOR_MASK)
        semi_instance = SemiSeparatedInstance(
            state=state,
            partition=CirclePartition(
                n_endpoints=6,
                left_boundary=0,
                top_boundary=2,
                right_boundary=3,
                bottom_boundary=5,
            ),
        )
        stats = SosaStats()

        family = list(iter_lemma_38_family(geometry=geometry, semi_instance=semi_instance, stats=stats))

        self.assertEqual(len(family), 1)
        full_instance = family[0]
        self.assertTrue(is_fully_separated_instance(geometry=geometry, full_instance=full_instance))
        self.assertTrue(
            set(semi_instance.partition.arc_positions("L")).issubset(
                set(full_instance.partition.arc_positions("L"))
            )
        )
        self.assertTrue(
            set(semi_instance.partition.arc_positions("R")).issubset(
                set(full_instance.partition.arc_positions("R"))
            )
        )

    def test_compute_lemma_38_family_handles_x_greater_than_one_case(self) -> None:
        geometry = geometry_from_endpoints(((0, 5), (1, 4), (2, 7), (3, 6)))
        state = state_from_allowed_masks(
            ALL_COLOR_MASK,
            ALL_COLOR_MASK,
            ALL_COLOR_MASK,
            ALL_COLOR_MASK,
        )
        semi_instance = SemiSeparatedInstance(
            state=state,
            partition=CirclePartition(
                n_endpoints=8,
                left_boundary=0,
                top_boundary=2,
                right_boundary=6,
                bottom_boundary=0,
            ),
        )
        stats = SosaStats()

        self.assertTrue(is_semi_separated_instance(geometry=geometry, semi_instance=semi_instance))
        family = list(iter_lemma_38_family(geometry=geometry, semi_instance=semi_instance, stats=stats))

        self.assertGreaterEqual(len(family), 1)
        self.assertTrue(solve_state_bruteforce(geometry, state))
        self.assertTrue(any(solve_state_bruteforce(geometry, child.state) for child in family))
        for full_instance in family:
            self.assertTrue(
                is_fully_separated_instance(geometry=geometry, full_instance=full_instance)
            )
            self.assertTrue(
                set(semi_instance.partition.arc_positions("L")).issubset(
                    set(full_instance.partition.arc_positions("L"))
                )
            )
            self.assertTrue(
                set(semi_instance.partition.arc_positions("R")).issubset(
                    set(full_instance.partition.arc_positions("R"))
                )
            )

    def test_compute_lemma_38_family_preserves_no_instance_existence(self) -> None:
        geometry = geometry_from_endpoints(((0, 5), (1, 4), (2, 7), (3, 6)))
        red_only = color_to_mask(Color.RED)
        state = state_from_allowed_masks(red_only, red_only, red_only, red_only)
        semi_instance = SemiSeparatedInstance(
            state=state,
            partition=CirclePartition(
                n_endpoints=8,
                left_boundary=0,
                top_boundary=2,
                right_boundary=6,
                bottom_boundary=0,
            ),
        )
        stats = SosaStats()

        family = list(iter_lemma_38_family(geometry=geometry, semi_instance=semi_instance, stats=stats))

        self.assertFalse(solve_state_bruteforce(geometry, state))
        self.assertFalse(any(solve_state_bruteforce(geometry, child.state) for child in family))


class SosaLemma33Tests(unittest.TestCase):
    def test_compute_lemma_33_family_returns_fully_separated_instances(self) -> None:
        geometry = geometry_from_endpoints(((0, 5), (1, 4), (2, 7), (3, 6)))
        state = state_from_allowed_masks(
            ALL_COLOR_MASK,
            ALL_COLOR_MASK,
            ALL_COLOR_MASK,
            ALL_COLOR_MASK,
        )
        stats = SosaStats()

        family = list(iter_lemma_33_family(geometry=geometry, state=state, stats=stats))

        self.assertGreaterEqual(len(family), 1)
        self.assertTrue(solve_state_bruteforce(geometry, state))
        self.assertTrue(any(solve_state_bruteforce(geometry, child.state) for child in family))
        for full_instance in family:
            self.assertTrue(
                is_fully_separated_instance(geometry=geometry, full_instance=full_instance)
            )


if __name__ == "__main__":
    unittest.main()
