import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.solvers.sosa.colors import Color, color_to_mask
from three_col_circle_code.solvers.sosa.reduction import apply_rr_exhaustively
from three_col_circle_code.solvers.sosa.types import SosaStats
from sosa_test_utils import geometry_from_endpoints, state_from_allowed_masks


class SosaReductionTests(unittest.TestCase):
    def test_apply_rr_exhaustively_removes_singleton_and_updates_neighbors(self) -> None:
        geometry = geometry_from_endpoints(((0, 2), (1, 3)))
        state = state_from_allowed_masks(
            color_to_mask(Color.RED),
            color_to_mask(Color.RED) | color_to_mask(Color.GREEN) | color_to_mask(Color.BLUE),
        )
        stats = SosaStats()

        reduced_state = apply_rr_exhaustively(
            geometry=geometry,
            state=state,
            stats=stats,
        )

        self.assertIsNotNone(reduced_state)
        assert reduced_state is not None
        self.assertFalse(reduced_state.state.is_active(0))
        self.assertTrue(reduced_state.state.is_active(1))
        self.assertEqual(
            reduced_state.state.allowed_color_masks[1],
            color_to_mask(Color.GREEN) | color_to_mask(Color.BLUE),
        )
        self.assertEqual(reduced_state.fixed_colors, ((0, color_to_mask(Color.RED)),))
        self.assertEqual(stats.rr_steps, 1)

    def test_apply_rr_exhaustively_cascades_until_fixpoint(self) -> None:
        geometry = geometry_from_endpoints(((0, 2), (1, 4), (3, 5)))
        state = state_from_allowed_masks(
            color_to_mask(Color.RED),
            color_to_mask(Color.RED) | color_to_mask(Color.GREEN),
            color_to_mask(Color.GREEN) | color_to_mask(Color.BLUE),
        )
        stats = SosaStats()

        reduced_state = apply_rr_exhaustively(
            geometry=geometry,
            state=state,
            stats=stats,
        )

        self.assertIsNotNone(reduced_state)
        assert reduced_state is not None
        self.assertEqual(reduced_state.state.active_vertices_mask, 0)
        self.assertEqual(
            reduced_state.fixed_colors,
            (
                (0, color_to_mask(Color.RED)),
                (1, color_to_mask(Color.GREEN)),
                (2, color_to_mask(Color.BLUE)),
            ),
        )
        self.assertEqual(stats.rr_steps, 3)

    def test_apply_rr_exhaustively_detects_empty_list_contradiction(self) -> None:
        geometry = geometry_from_endpoints(((0, 2), (1, 3)))
        state = state_from_allowed_masks(
            color_to_mask(Color.RED),
            color_to_mask(Color.RED),
        )
        stats = SosaStats()

        reduced_state = apply_rr_exhaustively(
            geometry=geometry,
            state=state,
            stats=stats,
        )

        self.assertIsNone(reduced_state)
        self.assertEqual(stats.rr_steps, 1)


if __name__ == "__main__":
    unittest.main()
