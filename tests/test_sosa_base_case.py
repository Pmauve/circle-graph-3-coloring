import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sosa_test_utils import graph_from_endpoints
from three_col_circle_code.solvers.sosa.base_case import solve_base_case_backtracking
from three_col_circle_code.solvers.sosa.colors import ALL_COLOR_MASK, RED_MASK
from three_col_circle_code.solvers.sosa.geometry import SosaGeometry
from three_col_circle_code.solvers.sosa.types import SosaSearchState, SosaStats


class SosaBaseCaseTests(unittest.TestCase):
    def test_backtracking_base_case_returns_witness_for_colorable_state(self) -> None:
        graph = graph_from_endpoints(((0, 3), (1, 4), (2, 5)))
        geometry = SosaGeometry.from_graph(graph)
        state = SosaSearchState.initial(n_vertices=geometry.n_vertices)
        stats = SosaStats()

        result = solve_base_case_backtracking(
            geometry=geometry,
            state=state,
            stats=stats,
            depth=0,
        )

        self.assertTrue(result.is_colorable)
        self.assertIsNotNone(result.witness)
        self.assertEqual(len(result.witness), geometry.n_vertices)
        self.assertEqual(stats.base_case_calls, 1)
        self.assertGreater(stats.base_case_search_nodes, 0)

    def test_backtracking_base_case_reports_unsat_for_empty_allowed_mask(self) -> None:
        graph = graph_from_endpoints(((0, 1),))
        geometry = SosaGeometry.from_graph(graph)
        state = SosaSearchState(
            active_vertices_mask=(1 << geometry.n_vertices) - 1,
            allowed_color_masks=(0,) + tuple(ALL_COLOR_MASK for _ in range(geometry.n_vertices - 1)),
        )
        stats = SosaStats()

        result = solve_base_case_backtracking(
            geometry=geometry,
            state=state,
            stats=stats,
            depth=2,
        )

        self.assertFalse(result.is_colorable)
        self.assertIsNone(result.witness)
        self.assertEqual(stats.base_case_calls, 1)
        self.assertEqual(stats.max_recursion_depth, 2)

    def test_backtracking_base_case_respects_allowed_color_masks(self) -> None:
        graph = graph_from_endpoints(((0, 2), (1, 3)))
        geometry = SosaGeometry.from_graph(graph)
        state = SosaSearchState(
            active_vertices_mask=(1 << geometry.n_vertices) - 1,
            allowed_color_masks=(RED_MASK,) + tuple(ALL_COLOR_MASK for _ in range(geometry.n_vertices - 1)),
        )
        stats = SosaStats()

        result = solve_base_case_backtracking(
            geometry=geometry,
            state=state,
            stats=stats,
            depth=0,
        )

        self.assertTrue(result.is_colorable)
        assert result.witness is not None
        self.assertEqual(result.witness[0], RED_MASK)


if __name__ == "__main__":
    unittest.main()
