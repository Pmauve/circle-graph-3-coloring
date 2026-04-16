import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.sat.baseline import BaselineSolveResult, LEGACY_PYSMT_MSAT, PYSAT_CADICAL
from three_col_circle_code.solvers.common import SOLVER_STATUS_ERROR, SOLVER_STATUS_OK
from three_col_circle_code.solvers.sat import (
    SAT_BASELINE_SOLVER,
    available_sat_solver_backends,
    solve_sat_solver,
)


class SatSolverTests(unittest.TestCase):
    def test_available_sat_solver_backends_lists_legacy_and_modern_backends(self) -> None:
        self.assertEqual(available_sat_solver_backends(), (LEGACY_PYSMT_MSAT, PYSAT_CADICAL))

    def test_solve_sat_solver_maps_success_result(self) -> None:
        graph = nx.path_graph(2)
        baseline_result = BaselineSolveResult(
            is_sat=True,
            elapsed_time=0.25,
            backend=PYSAT_CADICAL,
            n_vertices=2,
            m_edges=1,
        )

        with patch(
            "three_col_circle_code.solvers.sat.solve_3color_baseline",
            return_value=baseline_result,
        ) as solve, patch(
            "three_col_circle_code.solvers.sat.perf_counter",
            side_effect=(10.0, 10.4),
        ):
            result = solve_sat_solver(graph, backend=PYSAT_CADICAL, params={"seed": 1})

        solve.assert_called_once_with(graph, backend=PYSAT_CADICAL)
        self.assertEqual(result.solver, SAT_BASELINE_SOLVER)
        self.assertEqual(result.backend, PYSAT_CADICAL)
        self.assertEqual(result.status, SOLVER_STATUS_OK)
        self.assertTrue(result.is_three_colorable)
        self.assertAlmostEqual(result.wall_time_s, 0.4)
        self.assertEqual(result.details["requested_params"], {"seed": 1})
        self.assertIsNone(result.error)

    def test_solve_sat_solver_returns_error_result_instead_of_raising(self) -> None:
        graph = nx.complete_graph(4)

        with patch(
            "three_col_circle_code.solvers.sat.solve_3color_baseline",
            side_effect=RuntimeError("solver unavailable"),
        ):
            result = solve_sat_solver(graph, backend=PYSAT_CADICAL)

        self.assertEqual(result.status, SOLVER_STATUS_ERROR)
        self.assertEqual(result.backend, PYSAT_CADICAL)
        self.assertIsNone(result.is_three_colorable)
        self.assertEqual(result.error, "solver unavailable")
        self.assertEqual(result.n_vertices, 4)
        self.assertEqual(result.m_edges, 6)


if __name__ == "__main__":
    unittest.main()
