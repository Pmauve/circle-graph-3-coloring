import sys
import unittest
from importlib.util import find_spec
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sosa_test_utils import graph_from_endpoints
from three_col_circle_code.solvers.sosa.base_case import solve_base_case_sat
from three_col_circle_code.solvers.sosa.colors import ALL_COLOR_MASK, RED_MASK
from three_col_circle_code.solvers.sosa.geometry import SosaGeometry
from three_col_circle_code.solvers.sosa.types import SosaSearchState, SosaStats

HAS_PYSAT = find_spec("pysat") is not None


@unittest.skipUnless(HAS_PYSAT, "python-sat is required for the SOSA SAT base-case tests")
class SosaSatBaseCaseTests(unittest.TestCase):
    def test_sat_base_case_reports_sat_without_witness(self) -> None:
        graph = graph_from_endpoints(((0, 3), (1, 4), (2, 5)))
        geometry = SosaGeometry.from_graph(graph)
        state = SosaSearchState.initial(n_vertices=geometry.n_vertices)
        stats = SosaStats()

        result = solve_base_case_sat(
            geometry=geometry,
            state=state,
            stats=stats,
            depth=1,
        )

        self.assertTrue(result.is_colorable)
        self.assertIsNone(result.witness)
        self.assertEqual(stats.base_case_calls, 1)
        self.assertEqual(stats.max_recursion_depth, 1)

    def test_sat_base_case_reports_unsat_for_empty_allowed_mask(self) -> None:
        graph = graph_from_endpoints(((0, 2), (1, 3)))
        geometry = SosaGeometry.from_graph(graph)
        state = SosaSearchState(
            active_vertices_mask=(1 << geometry.n_vertices) - 1,
            allowed_color_masks=(0,) + tuple(ALL_COLOR_MASK for _ in range(geometry.n_vertices - 1)),
        )
        stats = SosaStats()

        result = solve_base_case_sat(
            geometry=geometry,
            state=state,
            stats=stats,
            depth=0,
        )

        self.assertFalse(result.is_colorable)
        self.assertIsNone(result.witness)

    def test_sat_base_case_respects_allowed_color_masks(self) -> None:
        graph = graph_from_endpoints(((0, 2), (1, 3)))
        geometry = SosaGeometry.from_graph(graph)
        state = SosaSearchState(
            active_vertices_mask=(1 << geometry.n_vertices) - 1,
            allowed_color_masks=(RED_MASK, RED_MASK),
        )
        stats = SosaStats()

        result = solve_base_case_sat(
            geometry=geometry,
            state=state,
            stats=stats,
            depth=0,
        )

        self.assertFalse(result.is_colorable)
        self.assertIsNone(result.witness)


if __name__ == "__main__":
    unittest.main()
