import sys
import unittest
from importlib.util import find_spec
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.solvers.common import SOLVER_STATUS_ERROR, SOLVER_STATUS_OK
from three_col_circle_code.solvers.sosa import SOSA_SOLVER, solve_sosa
from three_col_circle_code.solvers.sosa.colors import (
    Color,
    color_to_mask,
    mask_to_colors,
    mask_to_names,
)
from sosa_test_utils import graph_from_endpoints, is_valid_coloring_by_node

HAS_PYSAT = find_spec("pysat") is not None


class SosaSolverTests(unittest.TestCase):
    def test_sosa_color_wrapper_matches_mask_convention(self) -> None:
        mask = color_to_mask(Color.RED) | color_to_mask(Color.BLUE)

        self.assertEqual(mask_to_colors(mask), (Color.RED, Color.BLUE))
        self.assertEqual(mask_to_names(mask), ("red", "blue"))

    def test_sosa_solves_small_three_colorable_canonical_graph(self) -> None:
        graph = graph_from_endpoints(((0, 3), (1, 4), (2, 5)))

        result = solve_sosa(graph, params={"base_case_n": 8})

        self.assertEqual(result.solver, SOSA_SOLVER)
        self.assertEqual(result.status, SOLVER_STATUS_OK)
        self.assertTrue(result.is_three_colorable)
        self.assertEqual(result.details["implementation_status"], "paper-faithful-v1")
        self.assertEqual(
            result.details["config"],
            {
                "base_case_n": 8,
                "base_case_algorithm": "backtracking",
            },
        )
        self.assertGreater(result.details["solver_calls"], 0)
        self.assertEqual(result.details["base_case_calls"], 1)
        self.assertEqual(result.details["lemma_36_calls"], 0)
        self.assertEqual(result.details["rr_steps"], 0)
        self.assertTrue(is_valid_coloring_by_node(graph, result.details["coloring_by_node"]))

    def test_sosa_detects_small_non_three_colorable_canonical_graph(self) -> None:
        graph = graph_from_endpoints(((0, 4), (1, 5), (2, 6), (3, 7)))

        result = solve_sosa(graph, params={"base_case_n": 8})

        self.assertEqual(result.status, SOLVER_STATUS_OK)
        self.assertFalse(result.is_three_colorable)
        self.assertEqual(result.details["base_case_calls"], 1)
        self.assertNotIn("coloring_by_node", result.details)

    @unittest.skipUnless(HAS_PYSAT, "python-sat is required for the SOSA SAT-mode tests")
    def test_sosa_sat_mode_solves_small_three_colorable_graph_without_witness(self) -> None:
        graph = graph_from_endpoints(((0, 3), (1, 4), (2, 5)))

        result = solve_sosa(
            graph,
            params={"base_case_n": 8, "base_case_algorithm": "sat"},
        )

        self.assertEqual(result.solver, SOSA_SOLVER)
        self.assertEqual(result.status, SOLVER_STATUS_OK)
        self.assertTrue(result.is_three_colorable)
        self.assertEqual(
            result.details["config"],
            {
                "base_case_n": 8,
                "base_case_algorithm": "sat",
            },
        )
        self.assertEqual(result.details["base_case_calls"], 1)
        self.assertNotIn("coloring_by_node", result.details)

    @unittest.skipUnless(HAS_PYSAT, "python-sat is required for the SOSA SAT-mode tests")
    def test_sosa_sat_mode_detects_small_non_three_colorable_graph_without_witness(self) -> None:
        graph = graph_from_endpoints(((0, 4), (1, 5), (2, 6), (3, 7)))

        result = solve_sosa(
            graph,
            params={"base_case_n": 8, "base_case_algorithm": "sat"},
        )

        self.assertEqual(result.status, SOLVER_STATUS_OK)
        self.assertFalse(result.is_three_colorable)
        self.assertEqual(result.details["base_case_calls"], 1)
        self.assertNotIn("coloring_by_node", result.details)

    def test_sosa_rejects_invalid_parameters(self) -> None:
        graph = graph_from_endpoints(((0, 1),))

        result = solve_sosa(graph, params={"base_case_n": -1})

        self.assertEqual(result.solver, SOSA_SOLVER)
        self.assertEqual(result.status, SOLVER_STATUS_ERROR)
        self.assertIsNone(result.is_three_colorable)
        self.assertIsNone(result.wall_time_s)
        self.assertEqual(result.details["implementation_status"], "paper-faithful-v1")
        self.assertIn("invalid SOSA parameters", result.error)

    def test_sosa_solves_large_three_colorable_instance_recursively(self) -> None:
        graph = graph_from_endpoints(tuple((2 * i, 2 * i + 1) for i in range(9)))

        result = solve_sosa(graph, params={"base_case_n": 4})

        self.assertEqual(result.solver, SOSA_SOLVER)
        self.assertEqual(result.status, SOLVER_STATUS_OK)
        self.assertTrue(result.is_three_colorable)
        self.assertEqual(
            result.details["config"],
            {
                "base_case_n": 4,
                "base_case_algorithm": "backtracking",
            },
        )
        self.assertGreater(result.details["solver_calls"], 1)
        self.assertGreater(result.details["base_case_calls"], 1)
        self.assertGreater(result.details["lemma_36_calls"], 0)
        self.assertTrue(is_valid_coloring_by_node(graph, result.details["coloring_by_node"]))

    @unittest.skipUnless(HAS_PYSAT, "python-sat is required for the SOSA SAT-mode tests")
    def test_sosa_sat_mode_solves_large_three_colorable_instance_recursively_without_witness(self) -> None:
        graph = graph_from_endpoints(tuple((2 * i, 2 * i + 1) for i in range(9)))

        result = solve_sosa(
            graph,
            params={"base_case_n": 4, "base_case_algorithm": "sat"},
        )

        self.assertEqual(result.solver, SOSA_SOLVER)
        self.assertEqual(result.status, SOLVER_STATUS_OK)
        self.assertTrue(result.is_three_colorable)
        self.assertEqual(
            result.details["config"],
            {
                "base_case_n": 4,
                "base_case_algorithm": "sat",
            },
        )
        self.assertGreater(result.details["solver_calls"], 1)
        self.assertGreater(result.details["base_case_calls"], 1)
        self.assertGreater(result.details["lemma_36_calls"], 0)
        self.assertNotIn("coloring_by_node", result.details)

    @unittest.skipUnless(HAS_PYSAT, "python-sat is required for the SOSA SAT-mode tests")
    def test_sosa_sat_mode_detects_large_non_three_colorable_instance_recursively_without_witness(self) -> None:
        graph = graph_from_endpoints(
            (
                (0, 4),
                (1, 5),
                (2, 6),
                (3, 7),
                (8, 9),
                (10, 11),
                (12, 13),
                (14, 15),
                (16, 17),
            )
        )

        result = solve_sosa(
            graph,
            params={"base_case_n": 4, "base_case_algorithm": "sat"},
        )

        self.assertEqual(result.solver, SOSA_SOLVER)
        self.assertEqual(result.status, SOLVER_STATUS_OK)
        self.assertFalse(result.is_three_colorable)
        self.assertEqual(
            result.details["config"],
            {
                "base_case_n": 4,
                "base_case_algorithm": "sat",
            },
        )
        self.assertGreater(result.details["solver_calls"], 1)
        self.assertGreater(result.details["base_case_calls"], 1)
        self.assertNotIn("coloring_by_node", result.details)

    def test_sosa_detects_large_non_three_colorable_instance_recursively(self) -> None:
        graph = graph_from_endpoints(
            (
                (0, 4),
                (1, 5),
                (2, 6),
                (3, 7),
                (8, 9),
                (10, 11),
                (12, 13),
                (14, 15),
                (16, 17),
            )
        )

        result = solve_sosa(graph, params={"base_case_n": 4})

        self.assertEqual(result.solver, SOSA_SOLVER)
        self.assertEqual(result.status, SOLVER_STATUS_OK)
        self.assertFalse(result.is_three_colorable)
        self.assertEqual(
            result.details["config"],
            {
                "base_case_n": 4,
                "base_case_algorithm": "backtracking",
            },
        )
        self.assertGreater(result.details["solver_calls"], 1)
        self.assertGreater(result.details["base_case_calls"], 1)
        self.assertNotIn("coloring_by_node", result.details)

    @unittest.skipUnless(HAS_PYSAT, "python-sat is required for the SOSA SAT-mode tests")
    def test_sosa_backtracking_and_sat_agree_on_yes_no_answer(self) -> None:
        graphs = (
            graph_from_endpoints(((0, 3), (1, 4), (2, 5))),
            graph_from_endpoints(((0, 4), (1, 5), (2, 6), (3, 7))),
        )

        for graph in graphs:
            with self.subTest(n_vertices=graph.number_of_nodes(), edges=tuple(sorted(graph.edges()))):
                backtracking_result = solve_sosa(
                    graph,
                    params={"base_case_n": 8, "base_case_algorithm": "backtracking"},
                )
                sat_result = solve_sosa(
                    graph,
                    params={"base_case_n": 8, "base_case_algorithm": "sat"},
                )

                self.assertEqual(backtracking_result.status, SOLVER_STATUS_OK)
                self.assertEqual(sat_result.status, SOLVER_STATUS_OK)
                self.assertEqual(
                    backtracking_result.is_three_colorable,
                    sat_result.is_three_colorable,
                )

if __name__ == "__main__":
    unittest.main()
