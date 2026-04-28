import sys
import unittest
from pathlib import Path

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.sat.baseline import (
    LEGACY_PYSMT_MSAT,
    PYSAT_CADICAL,
    solve_3color_baseline,
)
from three_col_circle_code.solvers.common import SOLVER_STATUS_OK
from three_col_circle_code.solvers.sosa import solve_sosa_3_col_exact
from sosa_test_utils import (
    enumerate_endpoint_pairings,
    graph_from_endpoints,
    is_valid_coloring_by_node,
    random_endpoint_pairing,
)


class SosaCorrectnessVsSatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.oracle_backend = _detect_oracle_backend()
        if cls.oracle_backend is None:
            raise unittest.SkipTest("no SAT oracle backend is available in this environment")

    def test_sosa_matches_sat_exhaustively_up_to_four_vertices(self) -> None:
        for n_vertices in range(1, 5):
            for endpoint_pairs in enumerate_endpoint_pairings(n_vertices):
                graph = graph_from_endpoints(endpoint_pairs)
                self._assert_sosa_matches_sat(graph, base_case_n=3)

    def test_sosa_matches_sat_on_seeded_random_instances_up_to_eight_vertices(self) -> None:
        for n_vertices in range(5, 9):
            for seed in range(12):
                graph = graph_from_endpoints(
                    random_endpoint_pairing(n_vertices, seed=1000 * n_vertices + seed)
                )
                self._assert_sosa_matches_sat(graph, base_case_n=4)

    def _assert_sosa_matches_sat(self, graph: nx.Graph, *, base_case_n: int) -> None:
        sat_result = solve_3color_baseline(graph, backend=self.oracle_backend)
        sosa_result = solve_sosa_3_col_exact(graph, params={"base_case_n": base_case_n})

        self.assertEqual(
            sosa_result.status,
            SOLVER_STATUS_OK,
            msg=f"SOSA did not solve a canonical instance of size {graph.number_of_nodes()}",
        )
        self.assertEqual(
            sosa_result.is_colorable,
            sat_result.is_sat,
            msg=(
                "SOSA and SAT disagree for endpoint pairs "
                f"{_endpoint_pairs_from_graph(graph)} with backend {self.oracle_backend}"
            ),
        )
        if sosa_result.is_colorable:
            self.assertIn("coloring_by_node", sosa_result.details)
            self.assertTrue(is_valid_coloring_by_node(graph, sosa_result.details["coloring_by_node"]))
        else:
            self.assertNotIn("coloring_by_node", sosa_result.details)


def _detect_oracle_backend() -> str | None:
    trivial_graph = nx.path_graph(2)
    for backend in (PYSAT_CADICAL, LEGACY_PYSMT_MSAT):
        try:
            solve_3color_baseline(trivial_graph, backend=backend)
        except Exception:
            continue
        return backend
    return None


def _endpoint_pairs_from_graph(graph: nx.Graph) -> tuple[tuple[int, int], ...]:
    return tuple(
        sorted(
            (int(graph.nodes[node_id]["l"]), int(graph.nodes[node_id]["r"]))
            for node_id in graph.nodes()
        )
    )


if __name__ == "__main__":
    unittest.main()
